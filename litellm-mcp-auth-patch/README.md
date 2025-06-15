# LiteLLM MCP Authentication Patch

**Production-ready OAuth2 authentication and user cookie passthrough for LiteLLM MCP servers without code modifications.**

## What This Does

This patch adds OAuth2 authentication and user cookie passthrough to LiteLLM's Model Context Protocol (MCP) connections by replacing LiteLLM's global MCP manager with an enhanced version that supports:

- **Service-to-Service OAuth2** (client credentials flow)
- **User Cookie Passthrough** (forward user sessions)
- **Token Management** (automatic caching and refresh)
- **Zero Code Changes** to LiteLLM

## Quick Start

### 1. Install Dependencies

```bash
pip install litellm mcp httpx pydantic
```

### 2. Use the Patch

```python
from litellm_mcp_auth_patch import apply_mcp_auth_patch

# Configure OAuth2 for your MCP servers
config = {
    "mcp_servers": {
        "protected_server": {
            "url": "https://your-mcp-server.com/mcp",
            "transport": "http",
            "auth": {
                "oauth2": {
                    "token_url": "https://your-auth-server.com/oauth2/token",
                    "client_id": "your-client-id",
                    "client_secret": "your-client-secret"
                },
                "cookie_passthrough": {
                    "enabled": True,
                    "cookie_names": ["session_id"]
                }
            }
        }
    }
}

# Apply patch BEFORE using LiteLLM
apply_mcp_auth_patch(config)

# Now use LiteLLM normally - MCP authentication works automatically
import litellm
```

### 3. Environment Variables (Alternative)

```bash
export MCP_OAUTH2_TOKEN_URL="https://your-auth-server.com/oauth2/token"
export MCP_OAUTH2_CLIENT_ID="your-client-id"
export MCP_OAUTH2_CLIENT_SECRET="your-client-secret"
export LITELLM_ENABLE_MCP_AUTH_PATCH=true
```

```python
import litellm_mcp_auth_patch  # Automatically applies patch
```

### 4. Drop-in Replacement for `uv run litellm`

Instead of:
```bash
uv run litellm --config config.yaml --port 4000
```

Use:
```bash
export LITELLM_MCP_AUTH_AUTO_PATCH=true
uv run python litellm-mcp-auth-patch/litellm_with_mcp_auth.py --config config.yaml --port 4000
```

## Implementation Files

| File | Purpose |
|------|---------|
| `litellm_mcp_auth_patch.py` | **Main patch system** - replaces LiteLLM's MCP manager |
| `enhanced_mcp_server_manager.py` | Enhanced MCP manager with OAuth2 and cookie support |
| `mcp_auth_token_manager.py` | OAuth2 token acquisition and caching |
| `mcp_auth_config_schema.py` | Configuration models and validation |
| `litellm_with_mcp_auth.py` | Drop-in replacement wrapper script |
| `pyproject.toml` | Dependencies and project metadata |

## Configuration Options

### OAuth2 Configuration

```python
{
    "mcp_servers": {
        "server_name": {
            "url": "https://mcp-server.com/mcp",
            "transport": "http",  # or "sse"
            "auth": {
                "oauth2": {
                    "token_url": "https://auth.com/oauth2/token",
                    "client_id": "your-client-id",
                    "client_secret": "${SECRET_ENV_VAR}",  # Environment variable interpolation
                    "scope": "mcp:read mcp:write",         # Optional
                    "token_cache_ttl": 3600               # Optional, default 1 hour
                },
                "cookie_passthrough": {                   # Optional
                    "enabled": True,
                    "cookie_names": ["session_id", "user_id"]
                }
            }
        }
    }
}
```

### Global Configuration

```python
{
    "mcp_config": {
        "default_oauth2": {
            "token_url": "https://auth.com/oauth2/token",
            "client_id": "global-client-id",
            "client_secret": "${GLOBAL_SECRET}"
        },
        "default_cookie_passthrough": {
            "enabled": True
        }
    },
    "mcp_servers": {
        "server_name": {
            "url": "https://mcp-server.com/mcp",
            "transport": "http"
            # Uses global OAuth2 config automatically
        }
    }
}
```

## How It Works

1. **Patch Application**: `apply_mcp_auth_patch()` replaces LiteLLM's `global_mcp_server_manager`
2. **OAuth2 Flow**: Uses client credentials flow to acquire bearer tokens
3. **Header Injection**: Adds `Authorization: Bearer <token>` to MCP requests using MCP SDK's `headers` parameter
4. **Cookie Forwarding**: Passes user cookies from LiteLLM requests to MCP servers
5. **Transparent Operation**: Existing LiteLLM code works unchanged

## Authentication Flows

### Service Authentication (Startup)
```
LiteLLM → OAuth2 Server → Bearer Token → MCP Server Tools Discovery
```

### User Authentication (Runtime)
```
User Request → LiteLLM → MCP Server Tool Execution
   (cookies)            (Bearer token + user cookies)
```

## Deployment Patterns

### LiteLLM Proxy Integration

```python
from litellm_mcp_auth_patch import load_mcp_auth_config_for_litellm_proxy

def startup_hook(proxy_config):
    # Called during LiteLLM proxy startup
    enhanced_config = load_mcp_auth_config_for_litellm_proxy(proxy_config)
    return enhanced_config
```

### Docker Deployment

```dockerfile
FROM python:3.11

# Copy patch files
COPY litellm-mcp-auth-patch/ /app/mcp-auth-patch/
WORKDIR /app

# Install dependencies
RUN pip install litellm mcp httpx pydantic

# Set MCP authentication environment variables
ENV MCP_OAUTH2_TOKEN_URL="https://your-auth.com/oauth2/token"
ENV MCP_OAUTH2_CLIENT_ID="litellm-proxy"
ENV LITELLM_ENABLE_MCP_AUTH_PATCH=true

# Start with MCP authentication patch
CMD ["python", "-c", "import sys; sys.path.insert(0, 'mcp-auth-patch'); import litellm_mcp_auth_patch; import litellm; litellm.run_proxy()"]
```

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-mcp-auth-config
data:
  mcp-auth-config.json: |
    {
      "mcp_config": {
        "default_oauth2": {
          "token_url": "https://auth.company.com/oauth2/token",
          "client_id": "litellm-proxy",
          "client_secret": "${OAUTH2_CLIENT_SECRET}"
        },
        "default_cookie_passthrough": {
          "enabled": true
        }
      },
      "mcp_servers": {
        "company_tools": {
          "url": "https://tools.company.com/mcp",
          "transport": "http"
        }
      }
    }
```

## Testing

Run the validation suite to verify the patch works:

```bash
python testing/test_success_criteria.py
```

This validates:
- ✅ LiteLLM can be patched without source code modifications
- ✅ MCP authentication components integrate properly  
- ✅ Authentication configurations load correctly
- ✅ Auth header preparation works
- ✅ MCP SDK supports required authentication parameters

## Security Notes

- Client secrets should always be environment variables (`${VAR}` syntax)
- Tokens are cached in memory only (not persisted to disk)
- All OAuth2 requests use proper TLS validation
- User cookies are filtered based on configuration

## Troubleshooting

### Common Issues

1. **Import Order**: Always apply patch BEFORE importing LiteLLM
2. **Environment Variables**: Use `${VAR}` syntax for secrets in config files
3. **Network Access**: Ensure OAuth2 endpoint is reachable from LiteLLM
4. **Token Expiration**: Check `token_cache_ttl` if seeing frequent re-authentication

### Debug Mode

```python
import logging
logging.getLogger('litellm').setLevel(logging.DEBUG)
```

## Requirements

- Python 3.8+
- LiteLLM with MCP support
- MCP Python SDK
- OAuth2 server supporting client credentials flow
- Network access to OAuth2 and MCP endpoints

## License

MIT License