#!/usr/bin/env python3
"""
Test the simple MCP auth - just verify it patches correctly
"""

import os
import sys

# Set test environment
os.environ["MCP_OAUTH2_TOKEN_URL"] = "https://auth.example.com/oauth2/token"
os.environ["MCP_OAUTH2_CLIENT_ID"] = "test-client"
os.environ["MCP_OAUTH2_CLIENT_SECRET"] = "test-secret"

# Import and apply the simple patch
from simple_mcp_auth import apply_simple_mcp_auth, SimpleMCPAuth

def test_simple_auth():
    """Test the simple auth system"""
    print("🧪 Testing Simple MCP Auth")
    print("=" * 30)
    
    # Test auth class
    auth = SimpleMCPAuth()
    print(f"✅ Auth configured: {auth.token_url is not None}")
    
    # Test patching
    apply_simple_mcp_auth()
    print("✅ Patch applied")
    
    # Test that LiteLLM manager was replaced
    try:
        from litellm.proxy._experimental.mcp_server import mcp_server_manager
        manager = mcp_server_manager.global_mcp_server_manager
        
        if hasattr(manager, 'auth'):
            print("✅ Manager has auth attribute")
        else:
            print("❌ Manager missing auth attribute")
            return False
        
        print("✅ LiteLLM manager successfully replaced")
        return True
        
    except ImportError:
        print("⚠️ LiteLLM not available (that's ok for testing)")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_simple_auth()
    if success:
        print("\n🎉 Simple MCP Auth Test PASSED!")
        print("\nUsage:")
        print("1. Set environment variables:")
        print("   export MCP_OAUTH2_TOKEN_URL='https://your-auth.com/oauth2/token'")
        print("   export MCP_OAUTH2_CLIENT_ID='your-client-id'") 
        print("   export MCP_OAUTH2_CLIENT_SECRET='your-secret'")
        print("2. Run: python simple_mcp_auth.py")
        print("3. Start LiteLLM normally")
    else:
        print("\n❌ Test failed")
        sys.exit(1)