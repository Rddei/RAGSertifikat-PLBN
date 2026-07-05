import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# 1. PERBAIKAN: Import User, bukan Admin
from models.database import User, get_db
from models.schemas import LoginRequest
from security import verify_password, create_access_token

router = APIRouter()
logger = logging.getLogger("compliance.auth")


@router.post("/api/auth/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 2. PERBAIKAN: Gunakan model User
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.password):
        logger.warning("Login gagal untuk username: %s", request.username)
        raise HTTPException(401, "Username atau password salah")

    # Buat token (tetap menggunakan username sebagai subject)
    token = create_access_token(subject=user.username)
    
    # 3. PERBAIKAN: Kirimkan juga data 'role' agar bisa disimpan Frontend
    return {
        "access_token": token, 
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "role": user.role
        }
    }