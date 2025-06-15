# Simple LiteLLM MCP Authentication Solution

## The Problem

**LiteLLM Proxy has ZERO authentication when connecting to MCP servers.**

Two critical security gaps:
1. **Service Authentication** - Tool discovery happens with no auth
2. **User Session** - Tool execution has no user context

## The Solution

**One simple file that patches LiteLLM to add OAuth2 + cookie headers.**

- `simple_mcp_auth.py` - 100 lines solves both problems
- No complex configuration, no production complexity
- Just OAuth2 for service auth + cookies for user sessions

## How to Use

```bash
# Set credentials
export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
export MCP_OAUTH2_CLIENT_ID="litellm-proxy"
export MCP_OAUTH2_CLIENT_SECRET="your-secret"

# Apply patch
python simple_mcp_auth.py

# Run LiteLLM normally - now has authentication!
litellm --config config.yaml
```

## What Gets Added

**Tool Discovery (Startup)**:
- OAuth2 `Authorization: Bearer <token>` header
- MCP servers can verify LiteLLM's identity

**Tool Execution (Runtime)**:
- OAuth2 header for service identity
- User `Cookie` header for session context
- MCP servers get both service + user auth

## Key Insight

The MCP Python SDK already supports authentication via the `headers` parameter:
- `sse_client(url=server.url, headers=auth_headers)`
- `streamablehttp_client(url=server.url, headers=auth_headers)`

We just patch LiteLLM to use it!

## Files

- `simple_mcp_auth.py` - The complete solution
- `test_simple.py` - Basic verification test
- `README.md` - Usage instructions

**Ultra-simple. Ultra-effective. Ready to productionize later.**