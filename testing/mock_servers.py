"""
Mock OAuth2 and MCP Servers for Testing

This module provides mock implementations of:
1. OAuth2 token exchange endpoint
2. MCP server with OAuth2 validation
3. Test utilities for end-to-end authentication flow testing
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import parse_qs, urlparse
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


# OAuth2 Mock Server Models
class OAuth2TokenRequest(BaseModel):
    grant_type: str
    client_id: str
    client_secret: str
    scope: Optional[str] = None


class OAuth2TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: Optional[str] = None


# MCP Mock Server Models
class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPListToolsResponse(BaseModel):
    tools: List[MCPTool]


class MCPCallToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]


class MCPCallToolResponse(BaseModel):
    content: List[Dict[str, Any]]
    isError: bool = False


# Mock OAuth2 Server
class MockOAuth2Server:
    """Mock OAuth2 authorization server for testing"""
    
    def __init__(self):
        self.valid_clients = {
            "litellm-proxy": "secret123",
            "test-client": "test-secret",
            "specific-client-id": "specific-secret"
        }
        self.issued_tokens: Dict[str, Dict] = {}
    
    def create_app(self) -> FastAPI:
        app = FastAPI(title="Mock OAuth2 Server")
        
        @app.post("/oauth2/token", response_model=OAuth2TokenResponse)
        async def token_endpoint(request: Request):
            """OAuth2 token endpoint implementing client credentials flow"""
            
            # Parse form data
            form_data = await request.form()
            
            grant_type = form_data.get("grant_type")
            client_id = form_data.get("client_id")
            client_secret = form_data.get("client_secret")
            scope = form_data.get("scope")
            
            # Validate grant type
            if grant_type != "client_credentials":
                raise HTTPException(
                    status_code=400,
                    detail={"error": "unsupported_grant_type", "error_description": "Only client_credentials supported"}
                )
            
            # Validate client credentials
            if not client_id or not client_secret:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "invalid_request", "error_description": "Missing client credentials"}
                )
            
            if client_id not in self.valid_clients or self.valid_clients[client_id] != client_secret:
                raise HTTPException(
                    status_code=401,
                    detail={"error": "invalid_client", "error_description": "Invalid client credentials"}
                )
            
            # Generate token
            token_id = f"token_{int(time.time())}_{client_id}"
            access_token = f"mcp_access_token_{token_id}"
            expires_in = 3600  # 1 hour
            
            # Store token info for validation
            self.issued_tokens[access_token] = {
                "client_id": client_id,
                "scope": scope,
                "issued_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(seconds=expires_in)
            }
            
            return OAuth2TokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=expires_in,
                scope=scope
            )
        
        @app.get("/oauth2/validate")
        async def validate_token(authorization: str = Header(None)):
            """Token validation endpoint for debugging"""
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
            
            token = authorization[7:]  # Remove "Bearer " prefix
            
            if token not in self.issued_tokens:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            token_info = self.issued_tokens[token]
            if datetime.utcnow() > token_info["expires_at"]:
                raise HTTPException(status_code=401, detail="Token expired")
            
            return {"valid": True, "token_info": token_info}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy", "server": "Mock OAuth2 Server"}
        
        return app


# Mock MCP Server
class MockMCPServer:
    """Mock MCP server with OAuth2 authentication validation"""
    
    def __init__(self, oauth2_server: MockOAuth2Server):
        self.oauth2_server = oauth2_server
        self.tools = [
            MCPTool(
                name="weather_get",
                description="Get current weather for a location",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"]
                }
            ),
            MCPTool(
                name="time_get",
                description="Get current time",
                inputSchema={"type": "object", "properties": {}}
            ),
            MCPTool(
                name="user_profile_get",
                description="Get user profile (requires user context)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID"}
                    },
                    "required": ["user_id"]
                }
            )
        ]
    
    def validate_authorization(self, authorization: Optional[str]) -> Dict[str, Any]:
        """Validate OAuth2 Bearer token"""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = authorization[7:]  # Remove "Bearer " prefix
        
        if token not in self.oauth2_server.issued_tokens:
            raise HTTPException(
                status_code=401,
                detail="Invalid access token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token_info = self.oauth2_server.issued_tokens[token]
        if datetime.utcnow() > token_info["expires_at"]:
            raise HTTPException(
                status_code=401,
                detail="Access token expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return token_info
    
    def parse_user_cookies(self, cookie_header: Optional[str]) -> Dict[str, str]:
        """Parse user cookies from Cookie header"""
        cookies = {}
        if cookie_header:
            for cookie_pair in cookie_header.split(';'):
                if '=' in cookie_pair:
                    name, value = cookie_pair.strip().split('=', 1)
                    cookies[name] = value
        return cookies
    
    def create_app(self) -> FastAPI:
        app = FastAPI(title="Mock MCP Server")
        
        def get_auth_context(
            authorization: str = Header(None),
            cookie: Optional[str] = Header(None, alias="Cookie")
        ) -> Dict[str, Any]:
            """Extract authentication context from request"""
            # Validate OAuth2 token
            token_info = self.validate_authorization(authorization)
            
            # Parse user cookies
            user_cookies = self.parse_user_cookies(cookie)
            
            return {
                "token_info": token_info,
                "user_cookies": user_cookies
            }
        
        @app.get("/mcp/list_tools")
        async def list_tools(auth_context: Dict = Depends(get_auth_context)):
            """MCP list_tools endpoint with authentication"""
            return MCPListToolsResponse(tools=self.tools)
        
        @app.post("/mcp/call_tool")
        async def call_tool(
            request: MCPCallToolRequest,
            auth_context: Dict = Depends(get_auth_context)
        ):
            """MCP call_tool endpoint with authentication and user context"""
            
            tool_name = request.name
            arguments = request.arguments
            user_cookies = auth_context["user_cookies"]
            
            # Simulate tool execution
            if tool_name == "weather_get":
                location = arguments.get("location", "Unknown")
                return MCPCallToolResponse(
                    content=[{
                        "type": "text",
                        "text": f"The weather in {location} is sunny, 72°F"
                    }]
                )
            
            elif tool_name == "time_get":
                current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                return MCPCallToolResponse(
                    content=[{
                        "type": "text", 
                        "text": f"Current time: {current_time}"
                    }]
                )
            
            elif tool_name == "user_profile_get":
                # This tool requires user context from cookies
                session_id = user_cookies.get("session_id")
                user_id = user_cookies.get("user_id") or arguments.get("user_id")
                
                if not session_id:
                    return MCPCallToolResponse(
                        content=[{
                            "type": "text",
                            "text": "Error: User session required but no session_id cookie provided"
                        }],
                        isError=True
                    )
                
                return MCPCallToolResponse(
                    content=[{
                        "type": "text",
                        "text": f"User profile for {user_id or 'current user'} (session: {session_id}): John Doe, Premium Account"
                    }]
                )
            
            else:
                return MCPCallToolResponse(
                    content=[{
                        "type": "text",
                        "text": f"Error: Unknown tool '{tool_name}'"
                    }],
                    isError=True
                )
        
        @app.get("/health")
        async def health():
            return {"status": "healthy", "server": "Mock MCP Server"}
        
        return app


# Test Runner
class TestRunner:
    """Test runner for end-to-end OAuth2 MCP authentication flow"""
    
    def __init__(self):
        self.oauth2_server = MockOAuth2Server()
        self.mcp_server = MockMCPServer(self.oauth2_server)
    
    async def run_oauth2_server(self, port: int = 8080):
        """Run OAuth2 mock server"""
        app = self.oauth2_server.create_app()
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    
    async def run_mcp_server(self, port: int = 8081):
        """Run MCP mock server"""
        app = self.mcp_server.create_app()
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    
    async def run_both_servers(self):
        """Run both servers concurrently"""
        await asyncio.gather(
            self.run_oauth2_server(8080),
            self.run_mcp_server(8081)
        )


# Test Configuration Examples
TEST_CONFIG_YAML = """
# Test configuration for enhanced MCP authentication
mcp_config:
  default_oauth2:
    token_url: "http://localhost:8080/oauth2/token"
    client_id: "litellm-proxy"
    client_secret: "secret123"
    scope: "mcp:read mcp:write"
    token_cache_ttl: 3600
    timeout: 30.0
  
  default_cookie_passthrough:
    enabled: true
    cookie_names: ["session_id", "user_id"]

mcp_servers:
  mock_protected_server:
    url: "http://localhost:8081/mcp"
    transport: "http"
    description: "Mock MCP server with OAuth2 authentication"
    auth:
      oauth2:
        token_url: "http://localhost:8080/oauth2/token"
        client_id: "test-client"
        client_secret: "test-secret"
        scope: "mcp:read mcp:write"
      cookie_passthrough:
        enabled: true
        cookie_names: ["session_id", "user_id"]
"""

TEST_CONFIG_DICT = {
    "mcp_config": {
        "default_oauth2": {
            "token_url": "http://localhost:8080/oauth2/token",
            "client_id": "litellm-proxy",
            "client_secret": "secret123",
            "scope": "mcp:read mcp:write"
        },
        "default_cookie_passthrough": {
            "enabled": True,
            "cookie_names": ["session_id", "user_id"]
        }
    },
    "mcp_servers": {
        "mock_protected_server": {
            "url": "http://localhost:8081/mcp",
            "transport": "http",
            "description": "Mock MCP server with OAuth2 authentication",
            "auth": {
                "oauth2": {
                    "token_url": "http://localhost:8080/oauth2/token",
                    "client_id": "test-client",
                    "client_secret": "test-secret"
                },
                "cookie_passthrough": {
                    "enabled": True,
                    "cookie_names": ["session_id", "user_id"]
                }
            }
        }
    }
}


# CLI for running mock servers
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Run mock OAuth2 and MCP servers")
    parser.add_argument("--oauth2-port", type=int, default=8080, help="OAuth2 server port")
    parser.add_argument("--mcp-port", type=int, default=8081, help="MCP server port")
    parser.add_argument("--server", choices=["oauth2", "mcp", "both"], default="both", help="Which server to run")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    if args.server == "oauth2":
        print(f"Starting OAuth2 mock server on port {args.oauth2_port}...")
        asyncio.run(runner.run_oauth2_server(args.oauth2_port))
    elif args.server == "mcp":
        print(f"Starting MCP mock server on port {args.mcp_port}...")
        asyncio.run(runner.run_mcp_server(args.mcp_port))
    else:
        print(f"Starting both servers - OAuth2 on port {args.oauth2_port}, MCP on port {args.mcp_port}...")
        asyncio.run(runner.run_both_servers())