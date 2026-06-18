import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.database import Admin, get_db
from models.schemas import LoginRequest
from security import verify_password, create_access_token

router = APIRouter()
logger = logging.getLogger("compliance.auth")


@router.post("/api/auth/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Admin).where(Admin.username == request.username)
    )
    admin = result.scalar_one_or_none()

    # Verifikasi user + password. Pesan error disamakan agar tidak membocorkan
    # apakah username ada atau tidak (mencegah user enumeration).
    if admin is None or not verify_password(request.password, admin.password):
        logger.warning("Login gagal untuk username: %s", request.username)
        raise HTTPException(401, "Username atau password salah")

    token = create_access_token(subject=admin.username)
    return {"access_token": token, "token_type": "bearer"}
