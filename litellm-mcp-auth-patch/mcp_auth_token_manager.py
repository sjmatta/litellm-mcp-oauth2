"""
MCP Authentication Token Management System for LiteLLM

This module provides OAuth2 token acquisition, caching, and refresh functionality
for authenticating with MCP servers using the client credentials flow.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import httpx
import logging
from mcp_auth_config_schema import OAuth2Config, TokenCache, OAuth2GrantType
from get_credential import interpolate_credentials

logger = logging.getLogger(__name__)


class OAuth2TokenManager:
    """
    Manages OAuth2 tokens for MCP server authentication.
    
    Features:
    - Client credentials flow
    - Token caching with automatic expiration
    - Concurrent token refresh protection
    - Environment variable interpolation
    - Configurable timeouts
    """
    
    def __init__(self):
        self._token_cache: Dict[str, TokenCache] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._http_client = httpx.AsyncClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    def _get_cache_key(self, config: OAuth2Config) -> str:
        """Generate cache key for OAuth2 config"""
        return f"{config.token_url}:{config.client_id}:{config.scope or ''}"
    
    def _interpolate_credentials(self, value: str) -> str:
        """Interpolate credential references in config values"""
        return interpolate_credentials(value)
    
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
            
        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If response format is invalid
        """
        if not self._http_client:
            raise RuntimeError("OAuth2TokenManager not initialized - use async context manager")
        
        # Interpolate credential references
        client_id = self._interpolate_credentials(config.client_id)
        client_secret = self._interpolate_credentials(config.client_secret)
        token_url = self._interpolate_credentials(config.token_url)
        
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
            "Accept": "application/json",
            "User-Agent": "LiteLLM-MCP-OAuth2/1.0"
        }
        
        # Make token request
        try:
            logger.debug(f"Making OAuth2 token request to {token_url}")
            response = await self._http_client.post(
                token_url,
                data=request_data,
                headers=headers,
                timeout=config.timeout
            )
            response.raise_for_status()
            
        except httpx.HTTPError as e:
            logger.error(f"OAuth2 token request failed: {e}")
            raise
        
        # Parse response
        try:
            token_data = response.json()
        except Exception as e:
            logger.error(f"Invalid OAuth2 token response: {e}")
            raise ValueError(f"Invalid JSON response from token endpoint: {e}")
        
        # Validate required fields
        if "access_token" not in token_data:
            raise ValueError("OAuth2 response missing 'access_token' field")
        
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
    """
    Builds authentication headers for MCP requests.
    
    Combines OAuth2 tokens with user cookies and static headers.
    """
    
    def __init__(self, token_manager: OAuth2TokenManager):
        self.token_manager = token_manager
    
    async def build_headers(
        self,
        oauth2_config: Optional[OAuth2Config] = None,
        user_cookies: Optional[str] = None,
        static_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Build authentication headers for MCP request.
        
        Args:
            oauth2_config: OAuth2 configuration for service authentication
            user_cookies: User cookies to forward
            static_headers: Static headers to include
            
        Returns:
            Dictionary of headers to add to MCP request
        """
        headers = {}
        
        # Add OAuth2 authorization header
        if oauth2_config:
            auth_header = await self.token_manager.get_auth_header(oauth2_config)
            headers["Authorization"] = auth_header
        
        # Add user cookies
        if user_cookies:
            headers["Cookie"] = user_cookies
        
        # Add static headers
        if static_headers:
            headers.update(static_headers)
        
        # Add standard headers
        headers.update({
            "User-Agent": "LiteLLM-Proxy-MCP/1.0",
            "X-MCP-Client": "LiteLLM"
        })
        
        return headers


# Global token manager instance
_global_token_manager: Optional[OAuth2TokenManager] = None


async def get_global_token_manager() -> OAuth2TokenManager:
    """
    Get or create global OAuth2 token manager.
    
    Returns:
        Global OAuth2TokenManager instance
    """
    global _global_token_manager
    
    if _global_token_manager is None:
        _global_token_manager = OAuth2TokenManager()
        await _global_token_manager.__aenter__()
    
    return _global_token_manager


async def shutdown_global_token_manager():
    """Shutdown global token manager"""
    global _global_token_manager
    
    if _global_token_manager:
        await _global_token_manager.__aexit__(None, None, None)
        _global_token_manager = None


# Example usage
if __name__ == "__main__":
    async def example():
        """Example usage of OAuth2TokenManager"""
        
        # Create OAuth2 configuration
        config = OAuth2Config(
            token_url="https://auth.example.com/oauth2/token",
            client_id="litellm-proxy",
            client_secret="${OAUTH2_CLIENT_SECRET}",
            scope="mcp:read mcp:write",
            token_cache_ttl=3600
        )
        
        # Use token manager
        async with OAuth2TokenManager() as token_manager:
            # Get access token
            token = await token_manager.get_access_token(config)
            print(f"Access token: {token[:20]}...")
            
            # Get authorization header
            auth_header = await token_manager.get_auth_header(config)
            print(f"Auth header: {auth_header[:30]}...")
            
            # Build complete headers
            header_builder = MCPAuthHeaderBuilder(token_manager)
            headers = await header_builder.build_headers(
                oauth2_config=config,
                user_cookies="session=abc123; user_id=456",
                static_headers={"X-Custom": "value"}
            )
            print(f"Complete headers: {headers}")
            
            # Check cache stats
            stats = token_manager.get_cache_stats()
            print(f"Cache stats: {stats}")
    
    # Run example
    asyncio.run(example())