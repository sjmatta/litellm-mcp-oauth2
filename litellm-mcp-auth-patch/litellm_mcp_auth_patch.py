"""
LiteLLM MCP Authentication Patch

This module patches LiteLLM's MCP implementation to add OAuth2 authentication
and user cookie passthrough without modifying LiteLLM's source code. It works by:

1. Replacing the global MCP server manager with our enhanced version
2. Monkey patching import paths 
3. Providing configuration loading hooks
4. Maintaining full compatibility with existing LiteLLM interfaces

Usage:
    # Apply patch before importing/using LiteLLM
    from litellm_mcp_auth_patch import apply_mcp_auth_patch
    apply_mcp_auth_patch()
    
    # Now use LiteLLM normally - MCP authentication will work transparently
    import litellm
"""

import os
from typing import Dict, Any, Optional
from mcp_auth_config_schema import GlobalMCPConfig  
from enhanced_mcp_server_manager import EnhancedMCPServerManager
from mcp_auth_utils import ConfigurationLoader, ErrorHandler

# Track if patch has been applied
_PATCH_APPLIED = False
_ORIGINAL_MANAGER = None
_ENHANCED_MANAGER: Optional[EnhancedMCPServerManager] = None


def apply_mcp_auth_patch(config: Optional[Dict[str, Any]] = None):
    """
    Apply MCP authentication patch to LiteLLM's MCP implementation.
    
    This replaces LiteLLM's global MCP server manager with our enhanced version
    that supports OAuth2 authentication and user cookie passthrough using the MCP SDK's headers parameter.
    
    Args:
        config: Optional configuration dictionary with mcp_config and mcp_servers
               If not provided, will use environment variables or default config
    """
    global _PATCH_APPLIED, _ORIGINAL_MANAGER, _ENHANCED_MANAGER
    
    if _PATCH_APPLIED:
        print("⚠️ MCP authentication patch already applied")
        return
    
    print("🔧 Applying LiteLLM MCP authentication patch...")
    
    try:
        # Import LiteLLM's MCP manager module
        from litellm.proxy._experimental.mcp_server import mcp_server_manager
        
        # Store reference to original manager
        _ORIGINAL_MANAGER = mcp_server_manager.global_mcp_server_manager
        
        # Create enhanced manager (always sync creation)
        _ENHANCED_MANAGER = EnhancedMCPServerManager()
        if config and "mcp_servers" in config:
            _ENHANCED_MANAGER.load_servers_from_config(config["mcp_servers"])
        
        # Replace the global manager
        mcp_server_manager.global_mcp_server_manager = _ENHANCED_MANAGER
        
        # Also patch the module-level reference if it exists
        if hasattr(mcp_server_manager, 'MCPServerManager'):
            # Store original class
            _ORIGINAL_MANAGER_CLASS = mcp_server_manager.MCPServerManager
            # Replace with enhanced class
            mcp_server_manager.MCPServerManager = EnhancedMCPServerManager
        
        _PATCH_APPLIED = True
        print("✅ MCP authentication patch applied successfully")
        
    except ImportError as e:
        print(f"❌ Failed to apply MCP authentication patch - LiteLLM MCP module not found: {e}")
        raise
    except Exception as e:
        print(f"❌ Failed to apply MCP authentication patch: {e}")
        raise




def apply_mcp_auth_patch_from_env():
    """Apply MCP authentication patch using configuration from environment or files."""
    config = None
    
    # Try to load from config file first
    config_file = os.getenv("MCP_OAUTH2_CONFIG_FILE")
    if config_file:
        try:
            config = ConfigurationLoader.load_from_file(config_file)
            print(f"📋 Loaded MCP authentication config from {config_file}")
        except Exception as e:
            ErrorHandler.log_warning(print, f"Failed to load config file {config_file}", e)
    
    # Fall back to environment variables
    if not config:
        config = ConfigurationLoader.load_from_env()
        if config:
            print("📋 Built MCP authentication config from credential storage")
    
    # Apply patch
    apply_mcp_auth_patch(config)


def remove_mcp_auth_patch():
    """
    Remove MCP authentication patch and restore original LiteLLM MCP manager.
    
    This is useful for testing or if you need to disable MCP authentication.
    """
    global _PATCH_APPLIED, _ORIGINAL_MANAGER, _ENHANCED_MANAGER
    
    if not _PATCH_APPLIED:
        print("⚠️ MCP authentication patch not applied")
        return
    
    try:
        from litellm.proxy._experimental.mcp_server import mcp_server_manager
        
        # Restore original manager
        if _ORIGINAL_MANAGER:
            mcp_server_manager.global_mcp_server_manager = _ORIGINAL_MANAGER
        
        _PATCH_APPLIED = False
        _ENHANCED_MANAGER = None
        print("✅ MCP authentication patch removed")
        
    except Exception as e:
        print(f"❌ Failed to remove MCP authentication patch: {e}")


def get_enhanced_manager() -> Optional[EnhancedMCPServerManager]:
    """
    Get the current enhanced MCP manager if patch is applied.
    
    Returns:
        EnhancedMCPServerManager instance or None if patch not applied
    """
    return _ENHANCED_MANAGER if _PATCH_APPLIED else None


def is_patch_applied() -> bool:
    """Check if MCP authentication patch is currently applied"""
    return _PATCH_APPLIED


# Configuration loader for LiteLLM proxy integration
def load_mcp_auth_config_for_litellm_proxy(proxy_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load MCP authentication configuration for LiteLLM proxy startup.
    
    This function can be called during LiteLLM proxy startup to apply MCP authentication
    configuration before MCP servers are initialized.
    
    Args:
        proxy_config: LiteLLM proxy configuration dictionary
        
    Returns:
        Updated proxy configuration with MCP authentication patch applied
    """
    # Extract MCP configuration if present
    mcp_config = {}
    
    if "mcp_config" in proxy_config:
        mcp_config["mcp_config"] = proxy_config["mcp_config"]
    
    if "mcp_servers" in proxy_config:
        mcp_config["mcp_servers"] = proxy_config["mcp_servers"]
    
    # Apply patch if MCP configuration found
    if mcp_config:
        apply_mcp_auth_patch(mcp_config)
        print("✅ MCP authentication enabled for LiteLLM proxy")
    else:
        # Try environment-based configuration
        apply_mcp_auth_patch_from_env()
    
    return proxy_config


# Integration hook for LiteLLM proxy startup
def integrate_with_litellm_proxy():
    """
    Integration hook for LiteLLM proxy startup.
    
    This can be called in LiteLLM proxy startup scripts to automatically
    enable MCP authentication without code changes.
    """
    # Try to patch as early as possible
    try:
        apply_mcp_auth_patch_from_env()
    except Exception as e:
        print(f"⚠️ MCP authentication integration failed: {e}")


# Auto-patch if imported with specific environment variable
if os.getenv("LITELLM_ENABLE_MCP_AUTH_PATCH", "false").lower() == "true":
    print("🔧 Auto-applying MCP authentication patch due to LITELLM_ENABLE_MCP_AUTH_PATCH=true")
    apply_mcp_auth_patch_from_env()


if __name__ == "__main__":
    print("LiteLLM MCP Authentication Patch")
    print("=" * 40)
    print("This module patches LiteLLM to add OAuth2 authentication and user cookie passthrough for MCP servers.")
    print("\nKey functions:")
    print("- apply_mcp_auth_patch(config) - Apply patch with configuration")
    print("- apply_mcp_auth_patch_from_env() - Apply patch from environment variables")
    print("- remove_mcp_auth_patch() - Remove patch")
    print("- is_patch_applied() - Check if patch is applied")