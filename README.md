# LiteLLM MCP Authentication Solution

## The Problem

**LiteLLM Proxy has ZERO authentication when connecting to MCP servers.**

This creates two critical security gaps:

### 1. Service-to-Service Authentication Gap (Tool Discovery)
When LiteLLM Proxy starts up, it needs to discover what tools are available from MCP servers. This happens **out-of-band** from user requests - it's LiteLLM itself talking to MCP servers to build its tool registry.

**Current state:** ❌ No authentication - any MCP server must be completely open  
**Required:** ✅ OAuth2 client credentials flow for service authentication

### 2. User Session Authentication Gap (Tool Execution)
When a user makes a request through LiteLLM Proxy and it needs to call MCP tools, the MCP server needs the user's session context to authorize and personalize the tool execution.

**Current state:** ❌ No user context forwarded - MCP servers can't identify the user  
**Required:** ✅ User cookie passthrough to maintain session context

## The Solution

**Zero-modification monkey patch** that replaces LiteLLM's MCP manager with an enhanced version supporting both authentication flows.

### Key Insight: MCP SDK Already Supports Authentication
The MCP Python SDK has a `headers` parameter in both `sse_client()` and `streamablehttp_client()`. We leverage this existing capability.

### How It Works

```python
# Before: LiteLLM connects to MCP servers with no auth
await sse_client(url="https://mcp-server.com/mcp")

# After: Our enhanced manager injects authentication
await sse_client(url="https://mcp-server.com/mcp", headers={
    "Authorization": "Bearer <oauth2_token>",     # Service auth
    "Cookie": "session_id=<user_session>"        # User context
})
```

### Implementation Strategy

1. **Monkey Patch**: Replace `litellm.proxy._experimental.mcp_server.mcp_server_manager.global_mcp_server_manager`
2. **OAuth2 Flow**: Implement client credentials flow with token caching
3. **Cookie Forwarding**: Extract user cookies from LiteLLM requests and forward to MCP servers
4. **Zero Code Changes**: LiteLLM source remains untouched

## Quick Start

### 1. Install Dependencies
```bash
uv add litellm mcp pydantic httpx
```

### 2. Configure Authentication

For development (environment variables):
```bash
export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
export MCP_OAUTH2_CLIENT_ID="litellm-proxy"
export MCP_OAUTH2_CLIENT_SECRET="your-secret"
export LITELLM_MCP_AUTH_AUTO_PATCH=true
```

For production (secure credential storage):
Replace the `get_credential()` function in `get_credential.py` with your AWS Secrets Manager or equivalent secure storage implementation.

### 3. Use Drop-in Replacement
```bash
# Instead of: uv run litellm --config config.yaml --port 4000
# Use this:
uv run python litellm-mcp-auth-patch/litellm_with_mcp_auth.py --config config.yaml --port 4000
```

## Authentication Flows

### Flow 1: Service Authentication (Startup)
```
┌─────────────┐    OAuth2     ┌─────────────┐    Tools List    ┌─────────────┐
│ LiteLLM     │─────────────→ │ Auth Server │ ────────────────→│ MCP Server  │
│ Proxy       │               │             │                  │             │
│             │←──────────────│             │←─────────────────│ (Protected) │
└─────────────┘   JWT Token   └─────────────┘    + JWT Auth    └─────────────┘
```

### Flow 2: User Session (Runtime)
```
┌──────┐   User Request   ┌─────────────┐   Tool Call + Auth   ┌─────────────┐
│ User │─────────────────→│ LiteLLM     │─────────────────────→│ MCP Server  │
│      │   (with cookies) │ Proxy       │ (JWT + User Cookies) │             │
│      │                  │ + Patch     │                      │ (Protected) │
└──────┘                  └─────────────┘                      └─────────────┘
```

## Core Files

| File | Purpose |
|------|---------|
| `litellm_mcp_auth_patch.py` | **Main patch system** - replaces global MCP manager |
| `enhanced_mcp_server_manager.py` | Enhanced manager with OAuth2 + cookie support |
| `mcp_auth_token_manager.py` | OAuth2 client credentials + token caching |
| `mcp_auth_config_schema.py` | Pydantic configuration schemas |
| `litellm_with_mcp_auth.py` | **Drop-in CLI replacement** |

## Configuration Examples

### Basic OAuth2 Only
```python
{
    "mcp_config": {
        "default_oauth2": {
            "token_url": "https://auth.company.com/oauth2/token",
            "client_id": "litellm-proxy",
            "client_secret": "${MCP_OAUTH2_CLIENT_SECRET}"
        }
    },
    "mcp_servers": {
        "protected_server": {
            "url": "https://protected-mcp.company.com/mcp",
            "transport": "http"
        }
    }
}
```

### OAuth2 + Cookie Passthrough
```python
{
    "mcp_servers": {
        "user_aware_server": {
            "url": "https://user-tools.company.com/mcp",
            "auth": {
                "oauth2": {
                    "token_url": "https://auth.company.com/oauth2/token",
                    "client_id": "specific-client-id",
                    "client_secret": "${SPECIFIC_SECRET}"
                },
                "cookie_passthrough": {
                    "enabled": true,
                    "cookie_names": ["session_id", "user_context"]
                }
            }
        }
    }
}
```

## Validation

Verify the solution works:
```bash
python testing/test_success_criteria.py
```

Expected output:
```
🎯 SUCCESS CRITERIA TEST: MCP Authentication + LiteLLM MCP Integration
✅ CRITERION 1: Patch LiteLLM without code modifications
✅ CRITERION 2: MCP authentication capabilities integrated  
✅ CRITERION 3: Authentication configurations loaded
✅ CRITERION 4: Auth header preparation works
✅ CRITERION 5: MCP SDK supports required authentication parameters

🎊 SUCCESS: ALL CRITERIA MET!
🚀 READY FOR PRODUCTION with real MCP authentication endpoints!
```

## Why This Approach Works

1. **No Source Code Changes**: Uses monkey patching to enhance LiteLLM without modification
2. **Leverages Existing Capabilities**: MCP SDK already supports headers - we just use it
3. **Addresses Both Use Cases**: Service authentication AND user session forwarding
4. **Production Ready**: Includes proper error handling, token caching, and configuration
5. **Backwards Compatible**: Existing MCP servers continue to work unchanged

## Security Benefits

- ✅ **Service Authentication**: MCP servers can verify LiteLLM Proxy's identity
- ✅ **User Context Preservation**: MCP tools can personalize responses per user
- ✅ **Token Security**: OAuth2 tokens cached in memory only, automatic refresh
- ✅ **Cookie Filtering**: Configurable cookie passthrough for security
- ✅ **Zero Trust**: No open, unauthenticated MCP endpoints required

This solution transforms LiteLLM Proxy from an **authentication-free system** into a **properly secured service** that can safely connect to protected MCP servers while maintaining user context.