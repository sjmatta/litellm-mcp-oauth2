"""
Simple credential accessor function - replace with your secure implementation.

This is a stub that currently uses os.getenv() but provides the pattern
for replacing with AWS Secrets Manager or other secure credential storage.
"""

import os
from typing import Optional


def get_credential(key: str) -> Optional[str]:
    """
    Get a credential value. Replace this function with your secure implementation.
    
    Current implementation: Uses os.getenv() (insecure for production)
    Your implementation: Connect to AWS Secrets Manager or equivalent
    
    Args:
        key: Credential identifier (e.g., "MCP_OAUTH2_CLIENT_SECRET")
        
    Returns:
        Credential value or None if not found
        
    Example replacement for AWS Secrets Manager:
        import boto3
        client = boto3.client('secretsmanager')
        try:
            response = client.get_secret_value(SecretId=key)
            return response['SecretString']
        except Exception:
            return None
    """
    # TODO: Replace this with your secure credential storage
    return os.getenv(key)


def interpolate_credentials(value: str) -> str:
    """
    Interpolate credential references in configuration values.
    
    Supports ${CREDENTIAL_KEY} format for credential references.
    
    Args:
        value: Configuration value that may contain credential references
        
    Returns:
        Value with credentials interpolated
    """
    if value.startswith("${") and value.endswith("}"):
        credential_key = value[2:-1]
        credential_value = get_credential(credential_key)
        return credential_value if credential_value is not None else value
    
    return value