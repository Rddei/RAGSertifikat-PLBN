import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# 1. Pastikan model dan get_db diimpor dengan benar
from models.database import get_db, User
from security import decode_access_token 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
logger = logging.getLogger("compliance.dependencies")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau kadaluarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 2. Dekode token menghasilkan dictionary (misal: {"sub": "admin", "exp": ...})
    payload = decode_access_token(token)
    
    # 3. Ambil username dari key "sub" (subject)
    if payload is None:
        raise credentials_exception
        
    username = payload.get("sub")
    if username is None:
        raise credentials_exception
        
    # 4. Cari User di database berdasarkan username
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user

# 5. Tambahkan fungsi proteksi Admin jika diperlukan oleh rute lain
async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hak akses ditolak. Membutuhkan role admin."
        )
    return current_user