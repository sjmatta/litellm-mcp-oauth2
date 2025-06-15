# Simple LiteLLM MCP Authentication

**Problem**: LiteLLM Proxy has ZERO authentication when connecting to MCP servers.

**Solution**: Dead simple patch that adds OAuth2 + cookie headers to MCP requests.

## Quick Start

```bash
# 1. Set OAuth2 credentials
export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
export MCP_OAUTH2_CLIENT_ID="litellm-proxy"
export MCP_OAUTH2_CLIENT_SECRET="your-secret"

# 2. Apply the patch
python simple_mcp_auth.py

# 3. Run LiteLLM normally
litellm --config config.yaml
```

## What It Does

1. **Service Authentication**: Adds `Authorization: Bearer <token>` headers to MCP requests
2. **User Session**: Forwards user cookies to MCP servers for personalization

## How It Works

- Patches LiteLLM's global MCP manager with our simple version
- Gets OAuth2 tokens using client credentials flow
- Injects headers into MCP SDK calls via the `headers` parameter
- No LiteLLM source code modifications needed

## Files

- `simple_mcp_auth.py` - The entire solution (100 lines)
- `test_simple.py` - Basic test to verify it works

That's it! Keep it simple.