# security.py
"""Helper keamanan: hashing password & token JWT."""
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT
from passlib.context import CryptContext

from config import SECRET_KEY

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 jam


def hash_password(plain: str) -> str:
    """Ubah password plaintext menjadi hash bcrypt untuk disimpan."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Cocokkan password input dengan hash di database."""
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """Buat JWT yang ditandatangani dengan SECRET_KEY."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode & verifikasi JWT. Melempar jwt.PyJWTError bila invalid/kedaluwarsa."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
