# security.py
"""Helper keamanan: hashing password (bcrypt langsung) & token JWT.

Catatan: kita memakai library `bcrypt` secara langsung, BUKAN `passlib`.
`passlib` 1.7.4 sudah tidak di-maintain dan tidak kompatibel dengan bcrypt 4.x
(menyebabkan error "module 'bcrypt' has no attribute '__about__'" dan
"password cannot be longer than 72 bytes").
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt  # PyJWT

from config import SECRET_KEY

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 jam

# bcrypt hanya memakai maksimal 72 byte pertama dari password.
_BCRYPT_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    """Encode ke UTF-8 dan potong ke 72 byte (batasan bcrypt)."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Ubah password plaintext menjadi hash bcrypt untuk disimpan."""
    hashed = bcrypt.hashpw(_to_bytes(plain), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Cocokkan password input dengan hash di database. Aman terhadap hash invalid."""
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


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
