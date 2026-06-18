# dependencies.py
"""Dependency FastAPI untuk proteksi endpoint dengan Bearer token (JWT)."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from security import decode_access_token

# HTTPBearer cocok untuk login berbasis JSON: di /docs muncul kolom untuk
# menempelkan token, dan klien cukup mengirim header Authorization: Bearer <token>.
bearer_scheme = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Validasi Bearer token; kembalikan username admin bila valid."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise credentials_exc

    username = payload.get("sub")
    if not username:
        raise credentials_exc
    return username
