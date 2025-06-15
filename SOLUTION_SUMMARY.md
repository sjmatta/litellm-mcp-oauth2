# LiteLLM MCP Authentication Solution - Core Implementation

## Problem Statement

**LiteLLM Proxy lacks authentication when connecting to MCP servers, creating two critical security gaps:**

### Gap 1: Service-to-Service Authentication (Tool Discovery)
- **When**: LiteLLM Proxy startup, discovering available tools from MCP servers
- **Issue**: No service authentication - MCP servers must be completely open
- **Risk**: Any service can discover and potentially abuse MCP tools

### Gap 2: User Session Context (Tool Execution)  
- **When**: User requests trigger MCP tool calls via LiteLLM Proxy
- **Issue**: No user context forwarded - MCP servers can't identify the requesting user
- **Risk**: No personalization, authorization, or audit trail for tool usage

## Core Solution

**Monkey patch LiteLLM's MCP manager** to inject authentication headers using the MCP SDK's existing `headers` parameter.

### Key Technical Insight
```python
# MCP SDK already supports authentication via headers parameter:
from mcp.client.sse import sse_client

# Our enhancement:
async with sse_client(url=server_url, headers=auth_headers) as session:
    # Where auth_headers contains:
    # - "Authorization": "Bearer <oauth2_token>"  (service auth)
    # - "Cookie": "session_id=<user_session>"     (user context)
```

### Implementation Strategy

1. **Replace Global Manager**: `litellm.proxy._experimental.mcp_server.mcp_server_manager.global_mcp_server_manager`
2. **OAuth2 Client Credentials**: Authenticate LiteLLM service with OAuth2 servers  
3. **Cookie Passthrough**: Forward user cookies from incoming requests to MCP calls
4. **Zero Modifications**: LiteLLM source code remains untouched

## Authentication Flows

### Flow 1: Service Authentication (Startup/Tool Discovery)
```
LiteLLM Proxy Startup
        ↓
OAuth2 Token Request → Auth Server
        ↓                    ↓  
Bearer Token        ←─────────┘
        ↓
MCP Tool Discovery → MCP Server (with Bearer token)
        ↓                    ↓
Tool Registry       ←─────────┘
```

### Flow 2: User Session (Runtime/Tool Execution)
```
User Request (with cookies) → LiteLLM Proxy
                                    ↓
                         Extract: Bearer token + User cookies
                                    ↓
                         MCP Tool Call → MCP Server
                              (with both auths)    ↓
                         Tool Response ←─────────┘
                                    ↓
User Response          ←─────────────┘
```

## Core Files & Functions

### `litellm_mcp_auth_patch.py`
- **Function**: `apply_mcp_auth_patch(config)` 
- **Purpose**: Monkey patches LiteLLM's global MCP manager
- **Key**: Replaces `global_mcp_server_manager` with `EnhancedMCPServerManager`

### `enhanced_mcp_server_manager.py`
- **Function**: `_get_auth_headers(server_config, user_context)`
- **Purpose**: Builds authentication headers for MCP requests
- **Key**: Combines OAuth2 tokens + user cookies into single header dict

### `mcp_auth_token_manager.py`
- **Function**: `get_access_token(oauth2_config)`
- **Purpose**: OAuth2 client credentials flow with caching
- **Key**: Handles token refresh automatically

### `litellm_with_mcp_auth.py`
- **Function**: `main()`
- **Purpose**: Drop-in replacement for `uv run litellm`
- **Key**: Applies patch before starting LiteLLM

## Usage

### Simple Deployment
```bash
# Set authentication config
export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
export MCP_OAUTH2_CLIENT_ID="litellm-proxy"  
export MCP_OAUTH2_CLIENT_SECRET="your-secret"
export LITELLM_MCP_AUTH_AUTO_PATCH=true

# Replace litellm command
uv run python litellm-mcp-auth-patch/litellm_with_mcp_auth.py --config config.yaml
```

### Configuration
```python
{
    "mcp_servers": {
        "protected_tools": {
            "url": "https://tools.company.com/mcp",
            "auth": {
                "oauth2": {
                    "token_url": "https://auth.company.com/oauth2/token",
                    "client_id": "litellm-proxy",
                    "client_secret": "${SECRET}"
                },
                "cookie_passthrough": {
                    "enabled": true,
                    "cookie_names": ["session_id", "user_id"]
                }
            }
        }
    }
}
```

## Success Validation

Run `python testing/test_success_criteria.py` to verify:
- ✅ LiteLLM patches without source modification
- ✅ OAuth2 components integrate properly
- ✅ Authentication configs load correctly  
- ✅ Headers are built and injected properly
- ✅ MCP SDK supports required parameters

## Security Benefits

1. **Service Identity**: MCP servers can verify LiteLLM Proxy's legitimacy
2. **User Context**: MCP tools can personalize responses and enforce authorization
3. **Audit Trail**: All tool usage tied to authenticated users
4. **Zero Trust**: No open MCP endpoints required
5. **Token Security**: OAuth2 tokens cached in memory, auto-refresh

**Result**: Transforms LiteLLM from an insecure system into a properly authenticated service that can safely connect to protected MCP servers while preserving user context.