"""
MCP Authentication Token Management System for LiteLLM

This module provides OAuth2 token acquisition, caching, and refresh functionality
for authenticating with MCP servers using the client credentials flow.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
from mcp_auth_config_schema import OAuth2Config, TokenCache, OAuth2GrantType
from mcp_auth_utils import get_shared_http_client, AuthHeaderBuilder, ErrorHandler

logger = logging.getLogger(__name__)


class OAuth2TokenManager:
    """
    Manages OAuth2 tokens for MCP server authentication.
    
    Features:
    - Client credentials flow
    - Token caching with automatic expiration
    - Concurrent token refresh protection
    - Shared HTTP client management
    """
    
    def __init__(self):
        self._token_cache: Dict[str, TokenCache] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}
    
    def _get_cache_key(self, config: OAuth2Config) -> str:
        """Generate cache key for OAuth2 config"""
        return f"{config.token_url}:{config.client_id}:{config.scope or ''}"
    
    
    async def get_access_token(self, config: OAuth2Config) -> str:
        """
        Get a valid access token for the given OAuth2 configuration.
        
        This method:
        1. Checks cache for valid token
        2. If expired or missing, acquires new token
        3. Uses locks to prevent concurrent token refresh
        4. Returns Bearer token string
        
        Args:
            config: OAuth2 configuration
            
        Returns:
            Access token string (without "Bearer" prefix)
            
        Raises:
            httpx.HTTPError: If token request fails
            ValueError: If token response is invalid
        """
        cache_key = self._get_cache_key(config)
        
        # Check cache first
        cached_token = self._token_cache.get(cache_key)
        if cached_token and not cached_token.is_expired():
            logger.debug(f"Using cached token for {cache_key}")
            return cached_token.access_token
        
        # Get or create refresh lock for this config
        if cache_key not in self._refresh_locks:
            self._refresh_locks[cache_key] = asyncio.Lock()
        
        # Use lock to prevent concurrent token refresh
        async with self._refresh_locks[cache_key]:
            # Double-check cache after acquiring lock
            cached_token = self._token_cache.get(cache_key)
            if cached_token and not cached_token.is_expired():
                logger.debug(f"Using cached token after lock for {cache_key}")
                return cached_token.access_token
            
            # Acquire new token
            logger.info(f"Acquiring new OAuth2 token for {cache_key}")
            token = await self._acquire_token(config)
            self._token_cache[cache_key] = token
            
            return token.access_token
    
    async def _acquire_token(self, config: OAuth2Config) -> TokenCache:
        """
        Acquire a new OAuth2 token using client credentials flow.
        
        Args:
            config: OAuth2 configuration
            
        Returns:
            TokenCache object with new token
        """
        from get_credential import interpolate_credentials
        
        # Interpolate credential references
        client_id = interpolate_credentials(config.client_id)
        client_secret = interpolate_credentials(config.client_secret)
        token_url = interpolate_credentials(config.token_url)
        
        # Prepare token request
        request_data = {
            "grant_type": config.grant_type.value,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        
        if config.scope:
            request_data["scope"] = config.scope
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        # Make token request using shared HTTP client
        try:
            logger.debug(f"Making OAuth2 token request to {token_url}")
            http_client = await get_shared_http_client()
            response = await http_client.post(
                token_url,
                data=request_data,
                headers=headers,
                timeout=config.timeout
            )
            response.raise_for_status()
            
        except Exception as e:
            ErrorHandler.log_and_raise(logger, "OAuth2 token request failed", e)
        
        # Parse and validate response
        try:
            token_data = response.json()
            if "access_token" not in token_data:
                raise ValueError("OAuth2 response missing 'access_token' field")
        except Exception as e:
            ErrorHandler.log_and_raise(logger, "Invalid OAuth2 token response", e)
        
        # Calculate expiration time
        expires_in = token_data.get("expires_in", config.token_cache_ttl)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Create token cache entry
        token = TokenCache(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope", config.scope)
        )
        
        logger.info(f"Successfully acquired OAuth2 token, expires at {expires_at}")
        return token
    
    async def get_auth_header(self, config: OAuth2Config) -> str:
        """
        Get Authorization header value for the given OAuth2 configuration.
        
        Args:
            config: OAuth2 configuration
            
        Returns:
            Authorization header value (e.g., "Bearer abc123")
        """
        access_token = await self.get_access_token(config)
        return f"Bearer {access_token}"
    
    def clear_cache(self, config: Optional[OAuth2Config] = None):
        """
        Clear token cache.
        
        Args:
            config: If provided, only clear cache for this config.
                   If None, clear all cached tokens.
        """
        if config:
            cache_key = self._get_cache_key(config)
            self._token_cache.pop(cache_key, None)
            logger.debug(f"Cleared token cache for {cache_key}")
        else:
            self._token_cache.clear()
            logger.debug("Cleared all token cache")
    
    def get_cache_stats(self) -> Dict[str, dict]:
        """
        Get cache statistics for debugging.
        
        Returns:
            Dictionary with cache stats per configuration
        """
        stats = {}
        for cache_key, token in self._token_cache.items():
            stats[cache_key] = {
                "token_type": token.token_type,
                "expires_at": token.expires_at.isoformat(),
                "is_expired": token.is_expired(),
                "scope": token.scope,
                "access_token_preview": f"{token.access_token[:10]}..." if token.access_token else None
            }
        return stats


class MCPAuthHeaderBuilder:
    """Builds authentication headers for MCP requests using shared utilities."""
    
    def __init__(self, token_manager: OAuth2TokenManager):
        self.token_manager = token_manager
    
    async def build_headers(
        self,
        oauth2_config: Optional[OAuth2Config] = None,
        user_cookies: Optional[str] = None,
        static_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Build authentication headers for MCP request."""
        header_parts = [AuthHeaderBuilder.build_base_headers()]
        
        # Add OAuth2 authorization
        if oauth2_config:
            access_token = await self.token_manager.get_access_token(oauth2_config)
            header_parts.append(AuthHeaderBuilder.build_oauth2_header(access_token))
        
        # Add user cookies
        if user_cookies:
            header_parts.append(AuthHeaderBuilder.build_cookie_header(user_cookies))
        
        # Add static headers
        if static_headers:
            header_parts.append(static_headers)
        
        return AuthHeaderBuilder.combine_headers(*header_parts)


# Global token manager instance
_global_token_manager: Optional[OAuth2TokenManager] = None


def get_global_token_manager() -> OAuth2TokenManager:
    """Get or create global OAuth2 token manager."""
    global _global_token_manager
    
    if _global_token_manager is None:
        _global_token_manager = OAuth2TokenManager()
    
    return _global_token_manager


# Example usage
if __name__ == "__main__":
    async def example():
        """Example usage of OAuth2TokenManager"""
        from mcp_auth_config_schema import OAuth2Config
        
        config = OAuth2Config(
            token_url="https://auth.example.com/oauth2/token",
            client_id="litellm-proxy",
            client_secret="${OAUTH2_CLIENT_SECRET}"
        )
        
        # Use global token manager
        token_manager = get_global_token_manager()
        header_builder = MCPAuthHeaderBuilder(token_manager)
        
        headers = await header_builder.build_headers(
            oauth2_config=config,
            user_cookies="session=abc123"
        )
        print(f"Headers: {headers}")
    
    asyncio.run(example())