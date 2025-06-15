#!/usr/bin/env python3
"""
Test MCP integration with realistic scenarios.

This test validates that our authentication system works with MCP SDK components.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add our patch to path
sys.path.insert(0, str(Path(__file__).parent.parent / "litellm-mcp-auth-patch"))

from mcp_auth_config_schema import OAuth2Config, MCPAuthConfig, CookiePassthroughConfig
from enhanced_mcp_server_manager import EnhancedMCPServerManager
from mcp_auth_token_manager import OAuth2TokenManager, MCPAuthHeaderBuilder, get_global_token_manager
from mcp_auth_utils import CookieProcessor, AuthHeaderBuilder


async def test_mcp_sdk_compatibility():
    """Test that our code works with actual MCP SDK components"""
    
    print("🔌 MCP SDK COMPATIBILITY TEST")
    print("=" * 50)
    
    try:
        # Test MCP SDK imports that we use
        from mcp import ClientSession
        from mcp.client.sse import sse_client
        print("✅ MCP SDK core imports successful")
        
        # Test that sse_client accepts headers parameter
        import inspect
        sig = inspect.signature(sse_client)
        if 'headers' in sig.parameters:
            print("✅ MCP sse_client supports headers parameter")
        else:
            print("❌ MCP sse_client missing headers parameter")
            return False
        
        # Test HTTP client if available
        try:
            from mcp.client.streamable_http import streamablehttp_client
            sig = inspect.signature(streamablehttp_client)
            if 'headers' in sig.parameters:
                print("✅ MCP streamablehttp_client supports headers parameter")
            else:
                print("❌ MCP streamablehttp_client missing headers parameter")
                return False
        except ImportError:
            print("⚠️ MCP streamablehttp_client not available (optional)")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP SDK compatibility test failed: {e}")
        return False


async def test_header_building_integration():
    """Test that our header building works correctly with realistic scenarios"""
    
    print("\n🔧 HEADER BUILDING INTEGRATION TEST")
    print("=" * 50)
    
    try:
        # Test OAuth2 config creation
        oauth2_config = OAuth2Config(
            token_url="https://auth.example.com/oauth2/token",
            client_id="test-client",
            client_secret="test-secret"
        )
        print("✅ OAuth2Config created successfully")
        
        # Test cookie processing
        test_cookies = "session_id=abc123; user_id=456; other=xyz"
        filtered = CookieProcessor.filter_cookies(
            test_cookies,
            cookie_names=["session_id", "user_id"]
        )
        expected = "session_id=abc123; user_id=456"
        if filtered == expected:
            print("✅ Cookie filtering works correctly")
        else:
            print(f"❌ Cookie filtering failed: got '{filtered}', expected '{expected}'")
            return False
        
        # Test header building utilities
        auth_header = AuthHeaderBuilder.build_oauth2_header("test-token")
        if auth_header == {"Authorization": "Bearer test-token"}:
            print("✅ OAuth2 header building works")
        else:
            print(f"❌ OAuth2 header building failed: {auth_header}")
            return False
        
        cookie_header = AuthHeaderBuilder.build_cookie_header("test=value")
        if cookie_header == {"Cookie": "test=value"}:
            print("✅ Cookie header building works")
        else:
            print(f"❌ Cookie header building failed: {cookie_header}")
            return False
        
        # Test header combination
        combined = AuthHeaderBuilder.combine_headers(
            {"Authorization": "Bearer test"},
            {"Cookie": "session=123"},
            {"X-Custom": "value"},
            None  # Should be ignored
        )
        expected_combined = {
            "Authorization": "Bearer test",
            "Cookie": "session=123", 
            "X-Custom": "value"
        }
        if combined == expected_combined:
            print("✅ Header combination works")
        else:
            print(f"❌ Header combination failed: {combined}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Header building integration test failed: {e}")
        return False


async def test_enhanced_manager_integration():
    """Test the enhanced MCP server manager with realistic configuration"""
    
    print("\n🏗️ ENHANCED MANAGER INTEGRATION TEST") 
    print("=" * 50)
    
    try:
        # Create enhanced manager
        enhanced_manager = EnhancedMCPServerManager()
        print("✅ Enhanced manager created")
        
        # Test configuration loading with auth
        test_config = {
            "test_server": {
                "url": "https://test-mcp.example.com/mcp",
                "transport": "sse",
                "description": "Test server with authentication",
                "auth": {
                    "oauth2": {
                        "token_url": "https://auth.example.com/oauth2/token",
                        "client_id": "test-client",
                        "client_secret": "${TEST_SECRET}"
                    },
                    "cookie_passthrough": {
                        "enabled": True,
                        "cookie_names": ["session_id"]
                    }
                }
            }
        }
        
        enhanced_manager.load_servers_from_config(test_config)
        print("✅ Configuration loaded successfully")
        
        # Verify server was registered
        registry = enhanced_manager.get_registry()
        if len(registry) == 1:
            print("✅ Server registered in manager")
        else:
            print(f"❌ Expected 1 server, got {len(registry)}")
            return False
        
        # Verify auth config was stored
        server = list(registry.values())[0]
        if server.server_id in enhanced_manager.server_auth_configs:
            print("✅ Auth configuration stored")
        else:
            print("❌ Auth configuration not stored")
            return False
        
        # Test tool name mapping initialization
        enhanced_manager.initialize_tool_name_to_mcp_server_name_mapping()
        print("✅ Tool name mapping initialized")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced manager integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_auth_flow_simulation():
    """Simulate the authentication flow without making real network calls"""
    
    print("\n🔐 AUTHENTICATION FLOW SIMULATION")
    print("=" * 50)
    
    try:
        # Create enhanced manager with global auth config
        from mcp_auth_config_schema import GlobalMCPConfig
        
        global_config = GlobalMCPConfig(
            default_oauth2=OAuth2Config(
                token_url="https://auth.example.com/oauth2/token",
                client_id="global-client",
                client_secret="global-secret"
            ),
            default_cookie_passthrough=CookiePassthroughConfig(
                enabled=True,
                cookie_names=["session_id", "user_id"]
            )
        )
        
        enhanced_manager = EnhancedMCPServerManager(global_config)
        print("✅ Enhanced manager with global config created")
        
        # Add a server that uses global config
        server_config = {
            "global_auth_server": {
                "url": "https://global-mcp.example.com/mcp",
                "transport": "sse",
                "description": "Server using global auth config"
            }
        }
        
        enhanced_manager.load_servers_from_config(server_config)
        print("✅ Server configured to use global auth")
        
        # Initialize auth components
        enhanced_manager.initialize_auth()
        print("✅ Auth components initialized")
        
        # Verify components exist
        if enhanced_manager.token_manager is not None:
            print("✅ Token manager initialized")
        else:
            print("❌ Token manager not initialized")
            return False
        
        if enhanced_manager.header_builder is not None:
            print("✅ Header builder initialized")
        else:
            print("❌ Header builder not initialized")
            return False
        
        # Test that auth header building would work (will fail on network call)
        server = list(enhanced_manager.get_registry().values())[0]
        try:
            # This should fail when trying to get OAuth2 token, but the flow should start
            headers = await enhanced_manager._get_auth_headers(
                server,
                user_cookies="session_id=test123; user_id=456; other=ignore"
            )
            print("❌ Unexpected success - network call should have failed")
            return False
        except Exception as e:
            if any(keyword in str(e).lower() for keyword in ["connection", "token", "network", "resolve"]):
                print("✅ Auth flow triggered correctly (network request attempted)")
                print(f"   Expected network error: {type(e).__name__}")
                return True
            else:
                print(f"❌ Unexpected error in auth flow: {e}")
                return False
        
    except Exception as e:
        print(f"❌ Authentication flow simulation failed: {e}")
        return False


async def test_configuration_validation():
    """Test that our Pydantic models work correctly with various inputs"""
    
    print("\n📋 CONFIGURATION VALIDATION TEST")
    print("=" * 50)
    
    try:
        # Test valid configurations
        valid_oauth2 = OAuth2Config(
            token_url="https://auth.example.com/oauth2/token",
            client_id="test-client",
            client_secret="${SECRET}"
        )
        print("✅ Valid OAuth2 config accepted")
        
        # Test configuration with all optional fields
        full_oauth2 = OAuth2Config(
            token_url="https://auth.example.com/oauth2/token",
            client_id="test-client",
            client_secret="${SECRET}",
            scope="custom:scope",
            timeout=60,
            token_cache_ttl=7200
        )
        print("✅ Full OAuth2 config accepted")
        
        # Test cookie configuration
        cookie_config = CookiePassthroughConfig(
            enabled=True,
            cookie_names=["session", "user"],
            cookie_prefix="app_"
        )
        print("✅ Cookie passthrough config accepted")
        
        # Test complete auth configuration
        auth_config = MCPAuthConfig(
            oauth2=valid_oauth2,
            cookie_passthrough=cookie_config,
            static_headers={"X-API-Key": "test"}
        )
        print("✅ Complete auth config accepted")
        
        # Test server configuration
        from mcp_auth_config_schema import MCPServerConfig
        server_config = MCPServerConfig(
            url="https://test.example.com/mcp",
            transport="sse",
            auth=auth_config,
            description="Test server"
        )
        print("✅ Server config with auth accepted")
        
        # Test invalid configurations should fail
        try:
            invalid_oauth2 = OAuth2Config(
                token_url="",  # Empty URL
                client_id="",  # Empty client ID
                client_secret=""  # Empty secret
            )
            print("❌ Invalid OAuth2 config was accepted (should have failed)")
            return False
        except Exception:
            print("✅ Invalid OAuth2 config properly rejected")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation test failed: {e}")
        return False


async def main():
    """Run MCP integration tests"""
    
    print("🏆 MCP INTEGRATION TESTING")
    print("=" * 60)
    print("Testing integration with MCP SDK and realistic scenarios\n")
    
    results = []
    
    # Test MCP SDK compatibility
    result1 = await test_mcp_sdk_compatibility()
    results.append(("MCP SDK Compatibility", result1))
    
    # Test header building integration  
    result2 = await test_header_building_integration()
    results.append(("Header Building Integration", result2))
    
    # Test enhanced manager integration
    result3 = await test_enhanced_manager_integration()
    results.append(("Enhanced Manager Integration", result3))
    
    # Test authentication flow simulation
    result4 = await test_auth_flow_simulation()
    results.append(("Authentication Flow Simulation", result4))
    
    # Test configuration validation
    result5 = await test_configuration_validation()
    results.append(("Configuration Validation", result5))
    
    # Final results
    print("\n" + "=" * 60)
    print("🏁 MCP INTEGRATION TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎊 SUCCESS: ALL MCP INTEGRATION TESTS PASSED!")
        print("\n🎯 INTEGRATION VALIDATION COMPLETE:")
        print("   ✅ MCP SDK compatibility confirmed")
        print("   ✅ Header building works correctly") 
        print("   ✅ Enhanced manager integrates properly")
        print("   ✅ Authentication flow functions")
        print("   ✅ Configuration validation robust")
        print("\n🚀 READY FOR REAL MCP SERVER DEPLOYMENT!")
    else:
        print(f"\n⚠️ {len(results) - passed} test(s) failed")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)