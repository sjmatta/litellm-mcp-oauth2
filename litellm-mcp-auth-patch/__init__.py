"""
LiteLLM OAuth2 Authentication Patch

This package provides OAuth2 authentication for LiteLLM MCP connections
without requiring any modifications to LiteLLM's source code.

Usage:
    from litellm_oauth2_patch import apply_oauth2_patch
    
    config = {
        "mcp_servers": {
            "server": {
                "url": "https://mcp-server.com/mcp",
                "auth": {
                    "oauth2": {
                        "token_url": "https://auth.com/oauth2/token",
                        "client_id": "client-id",
                        "client_secret": "secret"
                    }
                }
            }
        }
    }
    
    apply_oauth2_patch(config)
    
    # Now use LiteLLM normally with OAuth2 authentication
    import litellm
"""

from .litellm_oauth2_patch import (
    apply_oauth2_patch,
    apply_oauth2_patch_from_env,
    remove_oauth2_patch,
    get_enhanced_manager,
    is_patch_applied,
    load_oauth2_config_for_litellm_proxy,
    integrate_with_litellm_proxy
)

from .oauth2_config_schema import (
    OAuth2Config,
    OAuth2GrantType,
    CookiePassthroughConfig,
    MCPAuthConfig,
    MCPServerConfig,
    GlobalMCPConfig,
    TokenCache
)

from .oauth2_token_manager import (
    OAuth2TokenManager,
    MCPAuthHeaderBuilder,
    get_global_token_manager,
    shutdown_global_token_manager
)

from .enhanced_mcp_server_manager import (
    EnhancedMCPServerManager,
    create_enhanced_manager_from_config,
    get_global_enhanced_manager
)

__version__ = "0.1.0"
__author__ = "OAuth2 MCP Team"
__description__ = "OAuth2 authentication for LiteLLM MCP connections"

__all__ = [
    # Main patch functions
    "apply_oauth2_patch",
    "apply_oauth2_patch_from_env", 
    "remove_oauth2_patch",
    "get_enhanced_manager",
    "is_patch_applied",
    "load_oauth2_config_for_litellm_proxy",
    "integrate_with_litellm_proxy",
    
    # Configuration models
    "OAuth2Config",
    "OAuth2GrantType",
    "CookiePassthroughConfig", 
    "MCPAuthConfig",
    "MCPServerConfig",
    "GlobalMCPConfig",
    "TokenCache",
    
    # OAuth2 components
    "OAuth2TokenManager",
    "MCPAuthHeaderBuilder",
    "get_global_token_manager",
    "shutdown_global_token_manager",
    
    # Enhanced manager
    "EnhancedMCPServerManager",
    "create_enhanced_manager_from_config",
    "get_global_enhanced_manager"
]