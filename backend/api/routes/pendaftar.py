"""Endpoint data master pendaftar (impor + daftar)."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_current_user
from models.database import Pendaftar, User, get_db
from services.pendaftar_service import import_master

router = APIRouter(prefix="/api/pendaftar", tags=["pendaftar"])
logger = logging.getLogger("compliance.pendaftar.api")


@router.post("/import")
async def import_pendaftar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Impor master pendaftar dari CSV/XLSX (kolom: id, nama, jurusan)."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File kosong")
    try:
        hasil = await import_master(db, data, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"filename": file.filename, **hasil}


@router.get("")
async def list_pendaftar(
    q: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Daftar pendaftar terimpor (opsional filter q pada id/nama)."""
    stmt = select(Pendaftar).order_by(Pendaftar.id_pendaftaran)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            Pendaftar.id_pendaftaran.like(like) | Pendaftar.nama.ilike(like)
        )
    rows = (await db.execute(stmt.limit(min(limit, 200)))).scalars().all()
    total = (await db.execute(select(func.count(Pendaftar.id)))).scalar()
    return {
        "total_terdaftar": total,
        "items": [
            {"id_pendaftaran": p.id_pendaftaran, "nama": p.nama,
             "jurusan_dituju": p.jurusan_dituju}
            for p in rows
        ],
    }
