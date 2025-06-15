"""
Enhanced MCP Server Manager with OAuth2 Authentication

This module extends LiteLLM's MCPServerManager to support OAuth2 authentication
using the MCP SDK's built-in headers parameter. It can be used as a drop-in
replacement for the existing MCPServerManager.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional, cast

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult
from mcp.types import Tool as MCPTool

# Import OAuth2 components
from mcp_auth_config_schema import (
    OAuth2Config, 
    MCPAuthConfig, 
    CookiePassthroughConfig,
    GlobalMCPConfig,
    MCPServerConfig
)
from mcp_auth_token_manager import OAuth2TokenManager, MCPAuthHeaderBuilder, get_global_token_manager

try:
    from mcp.client.streamable_http import streamablehttp_client
except ImportError:
    streamablehttp_client = None  # type: ignore

# Import LiteLLM types and utilities
from litellm._logging import verbose_logger
from litellm.proxy._types import (
    LiteLLM_MCPServerTable,
    MCPAuthType,
    MCPSpecVersion,
    MCPSpecVersionType,
    MCPTransport,
    MCPTransportType,
    UserAPIKeyAuth,
)
from litellm.types.mcp_server.mcp_server_manager import MCPInfo, MCPServer


class EnhancedMCPServerManager:
    """
    Enhanced MCP Server Manager with OAuth2 authentication support.
    
    This extends LiteLLM's existing MCPServerManager to add:
    - OAuth2 client credentials authentication
    - User cookie passthrough
    - Static header injection
    - Token caching and refresh
    """
    
    def __init__(self, global_config: Optional[GlobalMCPConfig] = None):
        # Core registry (same as original LiteLLM implementation)
        self.registry: Dict[str, MCPServer] = {}
        self.config_mcp_servers: Dict[str, MCPServer] = {}
        self.tool_name_to_mcp_server_name_mapping: Dict[str, str] = {}
        
        # OAuth2 authentication components
        self.global_config = global_config or GlobalMCPConfig()
        self.token_manager: Optional[OAuth2TokenManager] = None
        self.header_builder: Optional[MCPAuthHeaderBuilder] = None
        
        # Enhanced server configurations
        self.server_auth_configs: Dict[str, MCPAuthConfig] = {}
    
    async def initialize_auth(self):
        """Initialize OAuth2 authentication components"""
        if self.token_manager is None:
            self.token_manager = await get_global_token_manager()
            self.header_builder = MCPAuthHeaderBuilder(self.token_manager)
            verbose_logger.debug("Initialized OAuth2 authentication components")
    
    def get_registry(self) -> Dict[str, MCPServer]:
        """Get the registered MCP Servers from the registry and union with the config MCP Servers"""
        return self.config_mcp_servers | self.registry
    
    def load_servers_from_config(self, mcp_servers_config: Dict[str, Any]):
        """
        Load MCP Servers from configuration with enhanced authentication support.
        
        Supports both legacy LiteLLM format and new enhanced format with OAuth2.
        """
        verbose_logger.debug("Loading MCP Servers from enhanced config-----")
        
        for server_name, server_config in mcp_servers_config.items():
            # Parse enhanced server configuration
            if isinstance(server_config, dict):
                enhanced_config = MCPServerConfig(**server_config)
            else:
                enhanced_config = server_config
            
            # Create MCP server info
            _mcp_info: dict = server_config.get("mcp_info", {})
            mcp_info = MCPInfo(**_mcp_info)
            mcp_info["server_name"] = server_name
            mcp_info["description"] = enhanced_config.description
            
            server_id = str(uuid.uuid4())
            
            # Create server with enhanced config
            new_server = MCPServer(
                server_id=server_id,
                name=server_name,
                url=enhanced_config.url,
                transport=getattr(MCPTransport, enhanced_config.transport, MCPTransport.sse),
                spec_version=getattr(MCPSpecVersion, enhanced_config.spec_version.replace("-", "_").replace(".", "_"), MCPSpecVersion.mar_2025),
                auth_type=enhanced_config.auth_type,
                mcp_info=mcp_info,
            )
            
            # Store auth configuration separately
            if enhanced_config.auth:
                self.server_auth_configs[server_id] = enhanced_config.auth
                verbose_logger.debug(f"Stored auth config for server {server_name}")
            
            self.config_mcp_servers[server_id] = new_server
        
        verbose_logger.debug(
            f"Loaded Enhanced MCP Servers: {json.dumps(self.config_mcp_servers, indent=4, default=str)}"
        )
        
        self.initialize_tool_name_to_mcp_server_name_mapping()
    
    async def _get_auth_headers(
        self, 
        server: MCPServer, 
        user_cookies: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Build authentication headers for MCP server request.
        
        Args:
            server: MCP server configuration
            user_cookies: User cookies to forward (optional)
            
        Returns:
            Dictionary of headers to add to MCP request
        """
        await self.initialize_auth()
        
        # Get server-specific auth config or fall back to global config
        auth_config = self.server_auth_configs.get(server.server_id)
        
        oauth2_config = None
        cookie_passthrough_config = None
        static_headers = None
        
        if auth_config:
            oauth2_config = auth_config.oauth2
            cookie_passthrough_config = auth_config.cookie_passthrough
            static_headers = auth_config.static_headers
        
        # Fall back to global config if not specified per-server
        if not oauth2_config and self.global_config.default_oauth2:
            oauth2_config = self.global_config.default_oauth2
        
        if not cookie_passthrough_config and self.global_config.default_cookie_passthrough:
            cookie_passthrough_config = self.global_config.default_cookie_passthrough
        
        if not static_headers and self.global_config.default_headers:
            static_headers = self.global_config.default_headers
        
        # Process user cookies based on passthrough config
        processed_cookies = None
        if user_cookies and cookie_passthrough_config and cookie_passthrough_config.enabled:
            processed_cookies = self._process_user_cookies(user_cookies, cookie_passthrough_config)
        
        # Build headers using header builder
        if self.header_builder:
            headers = await self.header_builder.build_headers(
                oauth2_config=oauth2_config,
                user_cookies=processed_cookies,
                static_headers=static_headers
            )
        else:
            headers = {}
            if static_headers:
                headers.update(static_headers)
            if processed_cookies:
                headers["Cookie"] = processed_cookies
        
        verbose_logger.debug(f"Built auth headers for {server.name}: {list(headers.keys())}")
        return headers
    
    def _process_user_cookies(
        self, 
        user_cookies: str, 
        config: CookiePassthroughConfig
    ) -> Optional[str]:
        """
        Process user cookies based on passthrough configuration.
        
        Args:
            user_cookies: Raw cookie string from user request
            config: Cookie passthrough configuration
            
        Returns:
            Processed cookie string or None
        """
        if not config.enabled:
            return None
        
        # If no filtering specified, return all cookies
        if not config.cookie_names and not config.cookie_prefix:
            return user_cookies
        
        # Parse cookies and filter
        filtered_cookies = []
        cookie_pairs = [c.strip() for c in user_cookies.split(';') if c.strip()]
        
        for cookie_pair in cookie_pairs:
            if '=' not in cookie_pair:
                continue
            
            cookie_name = cookie_pair.split('=', 1)[0].strip()
            
            # Check cookie name filters
            include_cookie = False
            
            if config.cookie_names:
                include_cookie = cookie_name in config.cookie_names
            
            if config.cookie_prefix:
                include_cookie = include_cookie or cookie_name.startswith(config.cookie_prefix)
            
            if include_cookie:
                filtered_cookies.append(cookie_pair)
        
        return '; '.join(filtered_cookies) if filtered_cookies else None
    
    async def _get_tools_from_server(
        self, 
        server: MCPServer, 
        user_cookies: Optional[str] = None
    ) -> List[MCPTool]:
        """
        Get tools from MCP server with authentication support.
        
        Args:
            server: MCP server configuration
            user_cookies: User cookies to forward (optional)
            
        Returns:
            List of tools available on the server
        """
        verbose_logger.debug(f"Connecting to url: {server.url}")
        
        # Build authentication headers
        auth_headers = await self._get_auth_headers(server, user_cookies)
        
        verbose_logger.info("_get_tools_from_server with authentication...")
        
        # Connect using appropriate transport with auth headers
        if server.transport is None or server.transport == MCPTransport.sse:
            async with sse_client(url=server.url, headers=auth_headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    tools_result = await session.list_tools()
                    verbose_logger.debug(f"Tools from {server.name}: {tools_result}")
                    
                    # Update tool to server mapping
                    for tool in tools_result.tools:
                        self.tool_name_to_mcp_server_name_mapping[tool.name] = server.name
                    
                    return tools_result.tools
        
        elif server.transport == MCPTransport.http:
            if streamablehttp_client is None:
                verbose_logger.error(
                    "streamablehttp_client not available - install mcp with HTTP support"
                )
                raise ValueError(
                    "streamablehttp_client not available - please run `pip install mcp -U`"
                )
            
            verbose_logger.debug(f"Using HTTP streamable transport for {server.url}")
            async with streamablehttp_client(
                url=server.url,
                headers=auth_headers
            ) as (read_stream, write_stream, get_session_id):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    if get_session_id is not None:
                        session_id = get_session_id()
                        if session_id:
                            verbose_logger.debug(f"HTTP session ID: {session_id}")
                    
                    tools_result = await session.list_tools()
                    verbose_logger.debug(f"Tools from {server.name}: {tools_result}")
                    
                    # Update tool to server mapping
                    for tool in tools_result.tools:
                        self.tool_name_to_mcp_server_name_mapping[tool.name] = server.name
                    
                    return tools_result.tools
        else:
            verbose_logger.warning(f"Unsupported transport type: {server.transport}")
            return []
    
    async def call_tool(
        self, 
        name: str, 
        arguments: Dict[str, Any], 
        user_cookies: Optional[str] = None
    ):
        """
        Call a tool with authentication support.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            user_cookies: User cookies to forward (optional)
        """
        mcp_server = self._get_mcp_server_from_tool_name(name)
        if mcp_server is None:
            raise ValueError(f"Tool {name} not found")
        
        # Build authentication headers
        auth_headers = await self._get_auth_headers(mcp_server, user_cookies)
        
        if mcp_server.transport is None or mcp_server.transport == MCPTransport.sse:
            async with sse_client(url=mcp_server.url, headers=auth_headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(name, arguments)
        
        elif mcp_server.transport == MCPTransport.http:
            if streamablehttp_client is None:
                verbose_logger.error(
                    "streamablehttp_client not available - install mcp with HTTP support"
                )
                raise ValueError(
                    "streamablehttp_client not available - please run `pip install mcp -U`"
                )
            
            verbose_logger.debug(f"Using HTTP streamable transport for tool call: {name}")
            async with streamablehttp_client(
                url=mcp_server.url,
                headers=auth_headers
            ) as (read_stream, write_stream, get_session_id):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    if get_session_id is not None:
                        session_id = get_session_id()
                        if session_id:
                            verbose_logger.debug(f"HTTP session ID for tool call: {session_id}")
                    
                    return await session.call_tool(name, arguments)
        else:
            return CallToolResult(content=[], isError=True)
    
    # Original LiteLLM methods (for compatibility)
    
    def remove_server(self, mcp_server: LiteLLM_MCPServerTable):
        """Remove a server from the registry"""
        if mcp_server.alias in self.get_registry():
            del self.registry[mcp_server.alias]
            verbose_logger.debug(f"Removed MCP Server: {mcp_server.alias}")
        elif mcp_server.server_id in self.get_registry():
            del self.registry[mcp_server.server_id]
            verbose_logger.debug(f"Removed MCP Server: {mcp_server.server_id}")
        else:
            verbose_logger.warning(f"Server ID {mcp_server.server_id} not found in registry")
    
    def add_update_server(self, mcp_server: LiteLLM_MCPServerTable):
        """Add or update a server in the registry"""
        if mcp_server.server_id not in self.get_registry():
            new_server = MCPServer(
                server_id=mcp_server.server_id,
                name=mcp_server.alias or mcp_server.server_id,
                url=mcp_server.url,
                transport=cast(MCPTransportType, mcp_server.transport),
                spec_version=cast(MCPSpecVersionType, mcp_server.spec_version),
                auth_type=cast(MCPAuthType, mcp_server.auth_type),
                mcp_info=MCPInfo(
                    server_name=mcp_server.alias or mcp_server.server_id,
                    description=mcp_server.description,
                ),
            )
            self.registry[mcp_server.server_id] = new_server
            verbose_logger.debug(f"Added MCP Server: {mcp_server.alias or mcp_server.server_id}")
    
    async def get_allowed_mcp_servers(
        self, user_api_key_auth: Optional[UserAPIKeyAuth] = None
    ) -> List[str]:
        """Get the allowed MCP Servers for the user"""
        # Import here to avoid circular imports
        from litellm.proxy._experimental.mcp_server.auth.user_api_key_auth_mcp import (
            UserAPIKeyAuthMCP,
        )
        
        allowed_mcp_servers = await UserAPIKeyAuthMCP.get_allowed_mcp_servers(user_api_key_auth)
        verbose_logger.debug(f"Allowed MCP Servers for user api key auth: {allowed_mcp_servers}")
        
        if len(allowed_mcp_servers) > 0:
            return allowed_mcp_servers
        else:
            verbose_logger.debug(
                "No allowed MCP Servers found for user api key auth, returning default registry servers"
            )
            return list(self.get_registry().keys())
    
    async def list_tools(
        self, 
        user_api_key_auth: Optional[UserAPIKeyAuth] = None,
        user_cookies: Optional[str] = None
    ) -> List[MCPTool]:
        """
        List all tools available across all MCP Servers with authentication.
        
        Args:
            user_api_key_auth: User API key authentication
            user_cookies: User cookies to forward to MCP servers
            
        Returns:
            List[MCPTool]: Combined list of tools from all servers
        """
        allowed_mcp_servers = await self.get_allowed_mcp_servers(user_api_key_auth)
        
        list_tools_result: List[MCPTool] = []
        verbose_logger.debug("ENHANCED SERVER MANAGER LISTING TOOLS WITH AUTH")
        
        for server_id in allowed_mcp_servers:
            server = self.get_mcp_server_by_id(server_id)
            if server is None:
                verbose_logger.warning(f"MCP Server {server_id} not found")
                continue
            try:
                tools = await self._get_tools_from_server(server, user_cookies)
                list_tools_result.extend(tools)
            except Exception as e:
                verbose_logger.exception(f"Error listing tools from server {server.name}: {str(e)}")
        
        return list_tools_result
    
    def initialize_tool_name_to_mcp_server_name_mapping(self):
        """On startup, initialize the tool name to MCP server name mapping"""
        try:
            if asyncio.get_running_loop():
                asyncio.create_task(self._initialize_tool_name_to_mcp_server_name_mapping())
        except RuntimeError:  # no running event loop - this is expected in non-async contexts
            verbose_logger.debug(
                "No running event loop - tool mapping will be initialized on first tool listing"
            )
    
    async def _initialize_tool_name_to_mcp_server_name_mapping(self):
        """Call list_tools for each server and update the tool name to MCP server name mapping"""
        for server in self.get_registry().values():
            try:
                tools = await self._get_tools_from_server(server)
                for tool in tools:
                    self.tool_name_to_mcp_server_name_mapping[tool.name] = server.name
            except Exception as e:
                verbose_logger.exception(f"Error initializing tools for server {server.name}: {str(e)}")
    
    def _get_mcp_server_from_tool_name(self, tool_name: str) -> Optional[MCPServer]:
        """Get the MCP Server from the tool name"""
        if tool_name in self.tool_name_to_mcp_server_name_mapping:
            for server in self.get_registry().values():
                if server.name == self.tool_name_to_mcp_server_name_mapping[tool_name]:
                    return server
        return None
    
    def get_mcp_server_by_id(self, server_id: str) -> Optional[MCPServer]:
        """Get the MCP Server from the server id"""
        for server in self.get_registry().values():
            if server.server_id == server_id:
                return server
        return None


# Example usage and configuration loading
async def create_enhanced_manager_from_config(config_dict: Dict[str, Any]) -> EnhancedMCPServerManager:
    """
    Create EnhancedMCPServerManager from configuration dictionary.
    
    Args:
        config_dict: Configuration dictionary with mcp_config and mcp_servers
        
    Returns:
        Configured EnhancedMCPServerManager
    """
    # Parse global config
    global_config = None
    if "mcp_config" in config_dict:
        global_config = GlobalMCPConfig(**config_dict["mcp_config"])
    
    # Create manager
    manager = EnhancedMCPServerManager(global_config)
    
    # Load server configurations
    if "mcp_servers" in config_dict:
        manager.load_servers_from_config(config_dict["mcp_servers"])
    
    # Initialize authentication
    await manager.initialize_auth()
    
    return manager


# Global enhanced manager instance for compatibility
enhanced_global_mcp_server_manager: Optional[EnhancedMCPServerManager] = None


async def get_global_enhanced_manager() -> EnhancedMCPServerManager:
    """Get or create global enhanced MCP server manager"""
    global enhanced_global_mcp_server_manager
    
    if enhanced_global_mcp_server_manager is None:
        enhanced_global_mcp_server_manager = EnhancedMCPServerManager()
        await enhanced_global_mcp_server_manager.initialize_auth()
    
    return enhanced_global_mcp_server_manager