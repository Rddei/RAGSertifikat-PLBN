from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.database import Admin, get_db
import secrets

router = APIRouter()

class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)

@router.post("/api/auth/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.username == request.username))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(401, "Username atau Password salah")
    # In production use proper password verification
    if admin.password != request.password:
        raise HTTPException(401, "Username atau Password salah")
    token = secrets.token_hex(32)
    return {"message": "Login successful", "token": token}