#!/usr/bin/env python3
"""
LiteLLM wrapper with MCP authentication.

This script applies the MCP authentication patch and then runs LiteLLM exactly like 'uv run litellm'.
It's a drop-in replacement for the litellm command with OAuth2 and cookie passthrough support.

Usage (replaces 'uv run litellm'):
    # Set environment variables
    export LITELLM_MCP_AUTH_AUTO_PATCH=true
    export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
    export MCP_OAUTH2_CLIENT_ID="litellm-proxy"
    export MCP_OAUTH2_CLIENT_SECRET="your-secret"
    
    # Instead of: uv run litellm --config config.yaml --port 4000
    # Use this:   uv run python litellm_with_mcp_auth.py --config config.yaml --port 4000
"""

import os
import sys

def main():
    """Apply MCP authentication patch and run LiteLLM with original arguments"""
    
    # Add current directory to path to find our patch modules
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Apply MCP authentication patch if enabled
    if os.getenv("LITELLM_MCP_AUTH_AUTO_PATCH", "false").lower() == "true":
        print("🔧 Applying MCP authentication patch before starting LiteLLM...")
        try:
            from litellm_mcp_auth_patch import apply_mcp_auth_patch_from_env
            apply_mcp_auth_patch_from_env()
            print("✅ MCP authentication patch applied successfully")
        except Exception as e:
            print(f"⚠️ MCP authentication patch failed: {e}")
            print("⚠️ Continuing without MCP authentication...")
    
    # Now import and run LiteLLM exactly like the original CLI
    try:
        # Import LiteLLM's main CLI function
        from litellm.proxy.proxy_cli import run_server
        
        # Set sys.argv to make it look like we're running 'litellm' with the original args
        # sys.argv[0] is this script, sys.argv[1:] are the litellm arguments
        sys.argv[0] = 'litellm'  # Make it look like the original litellm command
        
        print(f"🚀 Starting LiteLLM with args: {' '.join(sys.argv[1:])}")
        
        # Run LiteLLM's proxy server with all the original arguments
        run_server()
        
    except ImportError:
        print("❌ LiteLLM not found. Install with: pip install litellm")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start LiteLLM: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()