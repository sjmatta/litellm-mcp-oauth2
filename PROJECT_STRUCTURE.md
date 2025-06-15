# Project Structure - LiteLLM MCP Authentication Solution

## Core Solution Files
```
litellm-mcp-auth-patch/
├── litellm_mcp_auth_patch.py          # 🔧 Main patch system - replaces LiteLLM's global MCP manager
├── enhanced_mcp_server_manager.py     # 🚀 Enhanced MCP manager with OAuth2 + cookie support  
├── mcp_auth_token_manager.py          # 🔑 OAuth2 client credentials flow + token caching
├── mcp_auth_config_schema.py          # 📋 Pydantic configuration schemas and validation
├── litellm_with_mcp_auth.py           # 🎯 Drop-in CLI replacement for 'uv run litellm'
├── README.md                          # 📚 Detailed implementation documentation
└── pyproject.toml                     # 📦 Dependencies and project metadata
```

## Documentation & Testing
```
├── README.md                          # 🎯 Main solution overview with problem/solution focus
├── SOLUTION_SUMMARY.md                # 📝 Core implementation details and flows
├── PROJECT_STRUCTURE.md               # 📊 This file - project organization
└── testing/
    ├── test_success_criteria.py       # ✅ Core validation tests (no network required)
    └── README.md                       # 📋 Testing documentation
```

## Configuration & Dependencies  
```
├── pyproject.toml                     # 📦 Main project dependencies
├── .gitignore                         # 🚫 Excludes cache files and LiteLLM repo
└── CLAUDE.md                          # 🤖 Claude Code session metadata
```

## Key Functions by File

### `litellm_mcp_auth_patch.py`
- `apply_mcp_auth_patch(config)` - Main entry point, replaces global MCP manager
- `apply_mcp_auth_patch_from_env()` - Environment variable-based configuration  
- `remove_mcp_auth_patch()` - Cleanup/restore original manager

### `enhanced_mcp_server_manager.py`
- `EnhancedMCPServerManager` - Drop-in replacement for LiteLLM's MCPServerManager
- `_get_auth_headers(server_config, user_context)` - Builds authentication headers
- `_create_mcp_session_with_auth()` - Creates authenticated MCP sessions

### `mcp_auth_token_manager.py`
- `OAuth2TokenManager.get_access_token()` - OAuth2 client credentials flow
- `MCPAuthHeaderBuilder.build_headers()` - Combines OAuth2 + cookies
- Token caching and automatic refresh logic

### `litellm_with_mcp_auth.py`
- `main()` - CLI wrapper that applies patch before starting LiteLLM
- Drop-in replacement for `uv run litellm` commands

## The Two Critical Authentication Flows

### 1. Service Authentication (Tool Discovery - Startup)
```
LiteLLM Proxy Startup
       ↓
OAuth2 Client Credentials → Auth Server  
       ↓                           ↓
Bearer Token              ←─────────┘
       ↓
Tool Discovery Request → MCP Server (with Bearer token)
       ↓                        ↓
Tool Registry          ←─────────┘
```

### 2. User Session Authentication (Tool Execution - Runtime)
```
User Request (with cookies) → LiteLLM Proxy
                                    ↓
                    Extract: Bearer token + User cookies  
                                    ↓
                    Tool Execution → MCP Server (with both auths)
                           ↓                ↓
                    Tool Response   ←────────┘
                           ↓
User Response      ←────────┘
```

## Usage Patterns

### Development/Testing
```bash
# Apply patch manually
python -c "from litellm_mcp_auth_patch import apply_mcp_auth_patch; apply_mcp_auth_patch()"

# Validate solution
python testing/test_success_criteria.py
```

### Production Deployment
```bash
# Set environment variables
export LITELLM_MCP_AUTH_AUTO_PATCH=true
export MCP_OAUTH2_TOKEN_URL="https://auth.company.com/oauth2/token"
export MCP_OAUTH2_CLIENT_ID="litellm-proxy"
export MCP_OAUTH2_CLIENT_SECRET="your-secret"

# Use drop-in replacement
uv run python litellm-mcp-auth-patch/litellm_with_mcp_auth.py --config config.yaml
```

## Security Model

- **Service Identity**: OAuth2 client credentials authenticate LiteLLM Proxy service
- **User Context**: User cookies forwarded to maintain session identity
- **Token Security**: OAuth2 tokens cached in memory only, automatic refresh
- **Zero Trust**: No open, unauthenticated MCP endpoints required
- **Audit Trail**: All tool usage tied to authenticated users

This transforms LiteLLM from an **authentication-free system** into a **properly secured service** that can safely connect to protected MCP servers while maintaining user context.