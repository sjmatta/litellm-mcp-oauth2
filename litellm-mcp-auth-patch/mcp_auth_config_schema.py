"""
MCP Authentication Configuration Schema for LiteLLM

This schema extends LiteLLM's existing MCP configuration to support OAuth2 authentication
and user cookie passthrough using the MCP SDK's built-in headers and auth parameters.
"""

from enum import Enum
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timedelta


class OAuth2GrantType(str, Enum):
    """OAuth2 grant types supported for MCP authentication"""
    CLIENT_CREDENTIALS = "client_credentials"
    AUTHORIZATION_CODE = "authorization_code"  # Future support


class OAuth2Config(BaseModel):
    """OAuth2 configuration for MCP server authentication"""
    model_config = ConfigDict(extra="forbid")
    
    # OAuth2 Server Configuration
    token_url: str = Field(..., description="OAuth2 token endpoint URL")
    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: str = Field(..., description="OAuth2 client secret")
    
    # Grant type (currently only client_credentials supported)
    grant_type: OAuth2GrantType = Field(
        default=OAuth2GrantType.CLIENT_CREDENTIALS,
        description="OAuth2 grant type"
    )
    
    # Optional parameters
    scope: Optional[str] = Field(
        default=None, 
        description="OAuth2 scopes to request"
    )
    
    # Token caching and refresh settings
    token_cache_ttl: int = Field(
        default=3600,
        description="Token cache TTL in seconds (default 1 hour)"
    )
    
    # HTTP timeout for token requests
    timeout: float = Field(
        default=30.0,
        description="Timeout for OAuth2 token requests in seconds"
    )


class CookiePassthroughConfig(BaseModel):
    """Configuration for user cookie passthrough"""
    model_config = ConfigDict(extra="forbid")
    
    enabled: bool = Field(
        default=True,
        description="Enable user cookie passthrough to MCP servers"
    )
    
    cookie_names: Optional[list[str]] = Field(
        default=None,
        description="Specific cookie names to forward (if None, forwards all)"
    )
    
    cookie_prefix: Optional[str] = Field(
        default=None,
        description="Only forward cookies with this prefix"
    )


class MCPAuthConfig(BaseModel):
    """Complete MCP authentication configuration"""
    model_config = ConfigDict(extra="forbid")
    
    # OAuth2 service-to-service authentication
    oauth2: Optional[OAuth2Config] = Field(
        default=None,
        description="OAuth2 configuration for service authentication"
    )
    
    # User cookie passthrough
    cookie_passthrough: Optional[CookiePassthroughConfig] = Field(
        default=None,
        description="Configuration for user cookie passthrough"
    )
    
    # Static headers (for testing or non-OAuth2 auth)
    static_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Static headers to add to all MCP requests"
    )


class MCPServerConfig(BaseModel):
    """Extended MCP server configuration with authentication support"""
    model_config = ConfigDict(extra="forbid")
    
    # Existing LiteLLM fields
    url: str = Field(..., description="MCP server URL")
    transport: str = Field(default="sse", description="Transport type (sse or http)")
    spec_version: str = Field(default="2025-03-26", description="MCP spec version")
    
    # Enhanced authentication configuration
    auth: Optional[MCPAuthConfig] = Field(
        default=None,
        description="Authentication configuration for this MCP server"
    )
    
    # Legacy auth_type field (for backwards compatibility)
    auth_type: Optional[str] = Field(
        default=None,
        description="Legacy auth type field (deprecated, use 'auth' instead)"
    )
    
    # Optional metadata
    alias: Optional[str] = Field(default=None, description="Human-readable server name")
    description: Optional[str] = Field(default=None, description="Server description")


class GlobalMCPConfig(BaseModel):
    """Global MCP configuration that can be shared across servers"""
    model_config = ConfigDict(extra="forbid")
    
    # Global OAuth2 configuration (used by servers that don't specify their own)
    default_oauth2: Optional[OAuth2Config] = Field(
        default=None,
        description="Default OAuth2 config for servers without specific auth"
    )
    
    # Global cookie passthrough settings
    default_cookie_passthrough: Optional[CookiePassthroughConfig] = Field(
        default=None,
        description="Default cookie passthrough settings"
    )
    
    # Global static headers
    default_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Default headers added to all MCP requests"
    )


class TokenCache(BaseModel):
    """OAuth2 token cache entry"""
    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime
    scope: Optional[str] = None
    
    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if token is expired (with buffer for early refresh)"""
        return datetime.utcnow() + timedelta(seconds=buffer_seconds) >= self.expires_at
    
    def to_auth_header(self) -> str:
        """Convert to Authorization header value"""
        return f"{self.token_type} {self.access_token}"


# Example configuration schemas
EXAMPLE_CONFIG_YAML = """
# Global MCP configuration
mcp_config:
  default_oauth2:
    token_url: "https://auth.company.com/oauth2/token"
    client_id: "litellm-proxy"
    client_secret: "${MCP_OAUTH2_CLIENT_SECRET}"
    scope: "mcp:read mcp:write"
    token_cache_ttl: 3600
  
  default_cookie_passthrough:
    enabled: true
    cookie_prefix: "session_"

# MCP servers with authentication
mcp_servers:
  protected_server:
    url: "https://protected-mcp.company.com/mcp"
    transport: "http"
    auth:
      oauth2:
        token_url: "https://auth.company.com/oauth2/token"
        client_id: "specific-client-id"
        client_secret: "${SPECIFIC_CLIENT_SECRET}"
      cookie_passthrough:
        enabled: true
        cookie_names: ["session_id", "user_context"]
  
  public_server:
    url: "https://public-mcp.example.com/mcp"
    transport: "sse"
    # No auth needed
  
  legacy_server:
    url: "https://legacy-mcp.example.com/mcp"
    auth_type: "bearer_token"  # Backwards compatibility
    auth:
      static_headers:
        Authorization: "Bearer ${LEGACY_TOKEN}"
"""

EXAMPLE_CONFIG_DICT = {
    "mcp_config": {
        "default_oauth2": {
            "token_url": "https://auth.company.com/oauth2/token",
            "client_id": "litellm-proxy",
            "client_secret": "${MCP_OAUTH2_CLIENT_SECRET}",
            "scope": "mcp:read mcp:write"
        }
    },
    "mcp_servers": {
        "protected_server": {
            "url": "https://protected-mcp.company.com/mcp",
            "transport": "http",
            "auth": {
                "oauth2": {
                    "token_url": "https://auth.company.com/oauth2/token",
                    "client_id": "specific-client-id", 
                    "client_secret": "${SPECIFIC_CLIENT_SECRET}"
                },
                "cookie_passthrough": {"enabled": True}
            }
        },
        "public_server": {
            "url": "https://public-mcp.example.com/mcp",
            "transport": "sse"
        }
    }
}