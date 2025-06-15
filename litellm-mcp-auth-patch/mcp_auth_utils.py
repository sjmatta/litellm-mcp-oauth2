"""
Shared utilities for MCP authentication system.

Consolidates common functionality to follow DRY principles:
- HTTP client management
- Configuration loading
- Error handling patterns  
- Logging utilities
"""

import asyncio
import json
import os
import yaml
from typing import Dict, Any, Optional, Union
import httpx
import logging
from get_credential import get_credential, interpolate_credentials

logger = logging.getLogger(__name__)


class HTTPClientManager:
    """Manages shared HTTP client lifecycle for OAuth2 and MCP requests."""
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create shared HTTP client."""
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0),
                    headers={"User-Agent": "LiteLLM-MCP-Auth/1.0"}
                )
            return self._client
    
    async def close(self):
        """Close HTTP client."""
        async with self._lock:
            if self._client:
                await self._client.aclose()
                self._client = None


class ConfigurationLoader:
    """Unified configuration loading with credential interpolation."""
    
    @staticmethod
    def load_from_file(file_path: str) -> Dict[str, Any]:
        """Load configuration from JSON or YAML file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            if file_path.endswith(('.yaml', '.yml')):
                config = yaml.safe_load(f)
            else:
                config = json.load(f)
        
        return ConfigurationLoader._interpolate_config(config)
    
    @staticmethod
    def load_from_env() -> Optional[Dict[str, Any]]:
        """Build configuration from environment variables."""
        token_url = get_credential("MCP_OAUTH2_TOKEN_URL")
        client_id = get_credential("MCP_OAUTH2_CLIENT_ID")
        client_secret = get_credential("MCP_OAUTH2_CLIENT_SECRET")
        
        if not all([token_url, client_id, client_secret]):
            return None
        
        return {
            "mcp_config": {
                "default_oauth2": {
                    "token_url": token_url,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": get_credential("MCP_OAUTH2_SCOPE") or "mcp:read mcp:write"
                },
                "default_cookie_passthrough": {
                    "enabled": (get_credential("MCP_COOKIE_PASSTHROUGH") or "true").lower() == "true"
                }
            }
        }
    
    @staticmethod
    def _interpolate_config(config: Union[Dict, list, str, Any]) -> Any:
        """Recursively interpolate credentials in configuration."""
        if isinstance(config, dict):
            return {k: ConfigurationLoader._interpolate_config(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [ConfigurationLoader._interpolate_config(item) for item in config]
        elif isinstance(config, str):
            return interpolate_credentials(config)
        else:
            return config


class CookieProcessor:
    """Utility for processing and filtering user cookies."""
    
    @staticmethod
    def filter_cookies(
        user_cookies: str,
        cookie_names: Optional[list] = None,
        cookie_prefix: Optional[str] = None
    ) -> Optional[str]:
        """
        Filter user cookies based on names or prefix.
        
        Args:
            user_cookies: Raw cookie string from user request
            cookie_names: List of specific cookie names to include
            cookie_prefix: Prefix for cookie names to include
            
        Returns:
            Filtered cookie string or None if no cookies match
        """
        if not user_cookies:
            return None
        
        # If no filtering specified, return all cookies
        if not cookie_names and not cookie_prefix:
            return user_cookies
        
        # Parse cookies and filter
        filtered_cookies = []
        cookie_pairs = [c.strip() for c in user_cookies.split(';') if c.strip()]
        
        for cookie_pair in cookie_pairs:
            if '=' not in cookie_pair:
                continue
            
            cookie_name = cookie_pair.split('=', 1)[0].strip()
            
            # Check cookie name filters
            include_cookie = False
            
            if cookie_names:
                include_cookie = cookie_name in cookie_names
            
            if cookie_prefix:
                include_cookie = include_cookie or cookie_name.startswith(cookie_prefix)
            
            if include_cookie:
                filtered_cookies.append(cookie_pair)
        
        return '; '.join(filtered_cookies) if filtered_cookies else None


class AuthHeaderBuilder:
    """Unified authentication header building service."""
    
    @staticmethod
    def build_oauth2_header(access_token: str) -> Dict[str, str]:
        """Build OAuth2 Authorization header."""
        return {"Authorization": f"Bearer {access_token}"}
    
    @staticmethod
    def build_cookie_header(cookies: str) -> Dict[str, str]:
        """Build Cookie header."""
        return {"Cookie": cookies}
    
    @staticmethod
    def build_base_headers() -> Dict[str, str]:
        """Build standard MCP client headers."""
        return {
            "User-Agent": "LiteLLM-Proxy-MCP/1.0",
            "X-MCP-Client": "LiteLLM",
            "Accept": "application/json"
        }
    
    @staticmethod
    def combine_headers(*header_dicts: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Combine multiple header dictionaries, skipping None values."""
        combined = {}
        for headers in header_dicts:
            if headers:
                combined.update(headers)
        return combined


class ErrorHandler:
    """Unified error handling with consistent logging."""
    
    @staticmethod
    def log_and_raise(logger_instance: logging.Logger, message: str, exception: Exception = None):
        """Log error and raise with consistent format."""
        if exception:
            logger_instance.error(f"{message}: {exception}")
            raise type(exception)(f"{message}: {exception}") from exception
        else:
            logger_instance.error(message)
            raise RuntimeError(message)
    
    @staticmethod
    def log_warning(logger_instance: logging.Logger, message: str, exception: Exception = None):
        """Log warning with consistent format."""
        if exception:
            logger_instance.warning(f"{message}: {exception}")
        else:
            logger_instance.warning(message)


# Global instances
_http_manager = HTTPClientManager()


async def get_shared_http_client() -> httpx.AsyncClient:
    """Get shared HTTP client instance."""
    return await _http_manager.get_client()


async def cleanup_shared_resources():
    """Cleanup shared resources."""
    await _http_manager.close()
