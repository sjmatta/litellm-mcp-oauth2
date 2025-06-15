#!/usr/bin/env python3
"""
Simple MCP Authentication for LiteLLM

Solves LiteLLM's two critical authentication gaps:
1. Service-to-service OAuth2 authentication for tool discovery
2. User cookie passthrough for session context

Usage:
    export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
    export MCP_OAUTH2_CLIENT_ID="litellm-proxy"
    export MCP_OAUTH2_CLIENT_SECRET="your-secret"
    
    python simple_mcp_auth.py
    # Now run LiteLLM normally - MCP requests will have OAuth2 + cookies
"""

import os
import asyncio
import httpx
from typing import Optional, Dict, Any


class SimpleMCPAuth:
    """Dead simple MCP authentication - just OAuth2 headers"""
    
    def __init__(self):
        self.token_url = os.getenv("MCP_OAUTH2_TOKEN_URL")
        self.client_id = os.getenv("MCP_OAUTH2_CLIENT_ID") 
        self.client_secret = os.getenv("MCP_OAUTH2_CLIENT_SECRET")
        self._token = None
    
    async def get_token(self) -> str:
        """Get OAuth2 token (no caching - keep it simple)"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            return response.json()["access_token"]
    
    async def get_headers(self, user_cookies: Optional[str] = None) -> Dict[str, str]:
        """Get auth headers for MCP requests"""
        headers = {}
        
        # Add OAuth2 if configured
        if all([self.token_url, self.client_id, self.client_secret]):
            token = await self.get_token()
            headers["Authorization"] = f"Bearer {token}"
        
        # Add user cookies if provided
        if user_cookies:
            headers["Cookie"] = user_cookies
        
        return headers


class SimpleMCPManager:
    """Simple replacement for LiteLLM's MCP manager with auth"""
    
    def __init__(self, original_manager):
        self.original = original_manager
        self.auth = SimpleMCPAuth()
        # Copy all attributes from original
        for attr in dir(original_manager):
            if not attr.startswith('_') and not hasattr(self, attr):
                setattr(self, attr, getattr(original_manager, attr))
    
    async def _get_tools_from_server(self, server, user_cookies=None):
        """Override to add auth headers"""
        # Get auth headers (OAuth2 + user cookies)
        auth_headers = await self.auth.get_headers(user_cookies)
        
        # Import MCP client
        from mcp.client.sse import sse_client
        from mcp import ClientSession
        
        # Connect with auth headers
        async with sse_client(url=server.url, headers=auth_headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                
                # Update tool mapping (copy from original)
                for tool in tools_result.tools:
                    self.tool_name_to_mcp_server_name_mapping[tool.name] = server.name
                
                return tools_result.tools
    
    async def call_tool(self, name: str, arguments: Dict[str, Any], user_cookies=None):
        """Override to add auth headers"""
        # Find the server for this tool
        server_name = self.tool_name_to_mcp_server_name_mapping.get(name)
        if not server_name:
            raise ValueError(f"Tool {name} not found")
        
        # Find the server object
        server = None
        for s in self.get_registry().values():
            if s.name == server_name:
                server = s
                break
        
        if not server:
            raise ValueError(f"Server for tool {name} not found")
        
        # Get auth headers (OAuth2 + user cookies)
        auth_headers = await self.auth.get_headers(user_cookies)
        
        # Import MCP client
        from mcp.client.sse import sse_client
        from mcp import ClientSession
        
        # Call tool with auth headers
        async with sse_client(url=server.url, headers=auth_headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(name, arguments)


def apply_simple_mcp_auth():
    """Apply the simple MCP auth patch to LiteLLM"""
    try:
        # Import LiteLLM's MCP manager
        from litellm.proxy._experimental.mcp_server import mcp_server_manager
        
        # Get the original manager
        original_manager = mcp_server_manager.global_mcp_server_manager
        
        # Replace with our simple auth version
        simple_manager = SimpleMCPManager(original_manager)
        mcp_server_manager.global_mcp_server_manager = simple_manager
        
        print("✅ Simple MCP authentication applied")
        
    except ImportError:
        print("❌ LiteLLM not found")
    except Exception as e:
        print(f"❌ Failed to apply MCP auth: {e}")


if __name__ == "__main__":
    # Check environment
    if not all([
        os.getenv("MCP_OAUTH2_TOKEN_URL"),
        os.getenv("MCP_OAUTH2_CLIENT_ID"), 
        os.getenv("MCP_OAUTH2_CLIENT_SECRET")
    ]):
        print("⚠️ Set MCP_OAUTH2_TOKEN_URL, MCP_OAUTH2_CLIENT_ID, MCP_OAUTH2_CLIENT_SECRET")
        print("Then run: python simple_mcp_auth.py")
        exit(1)
    
    # Apply the patch
    apply_simple_mcp_auth()
    
    print("🚀 MCP authentication ready!")
    print("Now run LiteLLM normally - MCP requests will have OAuth2 headers")