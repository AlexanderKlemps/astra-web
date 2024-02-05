import os
from fastapi import Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEYS = [os.getenv("API_KEY")]
auth_scheme = APIKeyHeader(name="x-api-key", auto_error=False)


def api_key_auth(api_key: str = Depends(auth_scheme)):
    if api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden"
        )
