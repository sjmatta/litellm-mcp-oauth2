# LiteLLM MCP OAuth2 Authentication

**Zero-modification OAuth2 authentication for LiteLLM's MCP server connections.**

## Project Structure

```
├── litellm-oauth2-patch/          # 🎯 IMPLEMENTATION - Deploy this
│   ├── litellm_oauth2_patch.py    # Main patch system
│   ├── enhanced_mcp_server_manager.py  # Enhanced MCP manager
│   ├── oauth2_token_manager.py    # OAuth2 token management
│   ├── oauth2_config_schema.py    # Configuration models
│   ├── __init__.py               # Package exports
│   ├── pyproject.toml            # Dependencies
│   └── README.md                 # Implementation docs
│
├── testing/                      # 🧪 VALIDATION - For testing only
│   ├── test_success_criteria.py  # Main validation script
│   ├── mock_servers.py          # Mock OAuth2/MCP servers
│   └── README.md                # Testing documentation
│
├── CLAUDE.md                     # Project development log
└── README.md                     # This overview
```

## What This Solves

LiteLLM Proxy currently has **no authentication support** when connecting to MCP servers. This implementation adds OAuth2 authentication that works in two scenarios:

1. **Service-to-Service (Startup)**: LiteLLM authenticates to MCP servers using OAuth2 bearer tokens during tool discovery
2. **User Passthrough (Runtime)**: LiteLLM forwards user cookies to MCP servers during tool execution

**The Goal**: Add OAuth2 authentication to LiteLLM Proxy's MCP client implementation without modifying LiteLLM's source code.

## How It Works

### The Breakthrough Discovery

1. **MCP Python SDK supports authentication**: Both `sse_client()` and `streamablehttp_client()` accept `headers` and `auth` parameters
2. **LiteLLM uses a global manager**: We can replace `global_mcp_server_manager` without modifying source code

### Implementation Strategy

```python
# BEFORE: LiteLLM makes unauthenticated MCP requests
response = requests.get(f"{mcp_server_url}/list_tools")

# AFTER: Enhanced manager adds OAuth2 authentication
headers = {"Authorization": f"Bearer {oauth2_token}"}
async with sse_client(url=server.url, headers=headers) as (read, write):
    # MCP requests now include OAuth2 authentication
```

### Authentication Flows

```
# Service-to-Service (Startup)
LiteLLM → OAuth2 Server → Bearer Token → MCP Server Tools Discovery

# User Passthrough (Runtime)  
User Request → LiteLLM → MCP Server Tool Execution
   (cookies)            (Bearer token + user cookies)
```

## Quick Start

### 1. Deploy the Implementation

Copy the `litellm-oauth2-patch/` directory to your deployment:

```bash
cp -r litellm-oauth2-patch/ /path/to/your/deployment/
```

### 2. Install Dependencies

```bash
pip install litellm mcp httpx pydantic
```

### 3. Apply the Patch

```python
import sys
sys.path.insert(0, '/path/to/litellm-oauth2-patch')

from litellm_oauth2_patch import apply_oauth2_patch

config = {
    "mcp_servers": {
        "protected_server": {
            "url": "https://protected-mcp.company.com/mcp",
            "transport": "http",
            "auth": {
                "oauth2": {
                    "token_url": "https://auth.company.com/oauth2/token",
                    "client_id": "litellm-proxy",
                    "client_secret": "${OAUTH2_CLIENT_SECRET}"
                }
            }
        }
    }
}

# Apply patch BEFORE importing LiteLLM
apply_oauth2_patch(config)

# Now use LiteLLM normally - OAuth2 works transparently!
import litellm
```

### 4. Environment Variables (Alternative)

```bash
export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
export MCP_OAUTH2_CLIENT_ID="litellm-proxy"
export MCP_OAUTH2_CLIENT_SECRET="your-secret-here"
export LITELLM_ENABLE_OAUTH2_PATCH=true
```

```python
import sys
sys.path.insert(0, '/path/to/litellm-oauth2-patch')
import litellm_oauth2_patch  # Automatically applies patch
```

## Validation

Test that everything works:

```bash
cd testing/
python test_success_criteria.py
```

Expected output:
```
🎊 SUCCESS: ALL CRITERIA MET!

🎯 DEPLOYMENT READINESS:
   ✅ OAuth2 authentication works with LiteLLM MCP
   ✅ No LiteLLM source code modifications required
   ✅ Service-to-service authentication supported
   ✅ User cookie passthrough supported
   ✅ Configuration schema validated

🚀 READY FOR PRODUCTION with real OAuth2 endpoints!
```

## Configuration Examples

### Basic OAuth2 Authentication

```yaml
mcp_servers:
  protected_server:
    url: "https://protected-mcp.company.com/mcp"
    transport: "http"
    auth:
      oauth2:
        token_url: "https://auth.company.com/oauth2/token"
        client_id: "litellm-proxy"
        client_secret: "${OAUTH2_CLIENT_SECRET}"
```

### OAuth2 + User Cookie Passthrough

```yaml
mcp_servers:
  user_context_server:
    url: "https://user-mcp.company.com/mcp"
    transport: "http"
    auth:
      oauth2:
        token_url: "https://auth.company.com/oauth2/token"
        client_id: "litellm-proxy"
        client_secret: "${OAUTH2_CLIENT_SECRET}"
      cookie_passthrough:
        enabled: true
        cookie_names: ["session_id", "user_id"]
```

### Global OAuth2 Configuration

```yaml
mcp_config:
  default_oauth2:
    token_url: "https://auth.company.com/oauth2/token"
    client_id: "litellm-proxy"
    client_secret: "${OAUTH2_CLIENT_SECRET}"
    scope: "mcp:read mcp:write"

mcp_servers:
  server1:
    url: "https://server1.company.com/mcp"
    # Uses global OAuth2 config
  
  server2:
    url: "https://server2.company.com/mcp"
    # Uses global OAuth2 config
```

## Success Criteria - ALL MET ✅

✅ **Configuration Success** - OAuth2 config loads without errors, environment variables work  
✅ **Service Authentication Success** - Bearer tokens acquired and used for MCP requests  
✅ **User Authentication Success** - Cookies forwarded with proper filtering  
✅ **End-to-End Integration Success** - Complete flow works from token acquisition to tool execution  
✅ **Single Container Success** - No external dependencies beyond OAuth2 endpoint  

## Implementation Details

The solution uses the **MCP SDK's built-in authentication support** combined with **monkey patching**:

1. **`litellm_oauth2_patch.py`**: Replaces LiteLLM's global MCP manager before it's used
2. **`enhanced_mcp_server_manager.py`**: Drop-in replacement that adds OAuth2 authentication using MCP SDK's `headers` parameter
3. **`oauth2_token_manager.py`**: Handles OAuth2 client credentials flow with token caching
4. **`oauth2_config_schema.py`**: Pydantic models for configuration validation

## Deployment Patterns

### Docker

```dockerfile
FROM python:3.11
COPY litellm-oauth2-patch/ /app/oauth2-patch/
WORKDIR /app
RUN pip install litellm mcp httpx pydantic

ENV MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
ENV MCP_OAUTH2_CLIENT_ID="litellm-proxy"
ENV LITELLM_ENABLE_OAUTH2_PATCH=true

CMD ["python", "-c", "import sys; sys.path.insert(0, 'oauth2-patch'); import litellm_oauth2_patch; import litellm; litellm.run_proxy()"]
```

### LiteLLM Proxy Integration

```python
from litellm_oauth2_patch import load_oauth2_config_for_litellm_proxy

def startup_hook(proxy_config):
    return load_oauth2_config_for_litellm_proxy(proxy_config)
```

## Why This Approach

**Compared to OAuth2 Proxy**: This approach is superior because:
- ✅ Fewer moving parts (no separate proxy process)
- ✅ Integrates directly with LiteLLM's MCP system
- ✅ Uses MCP SDK's intended authentication mechanism
- ✅ Maintains perfect API compatibility
- ✅ Single container deployment

**Compared to Code Modifications**: This approach is better because:
- ✅ No LiteLLM source code changes required
- ✅ Works with any LiteLLM version that supports MCP
- ✅ Easy to deploy and maintain
- ✅ Can be disabled/enabled dynamically

## License

MIT License