import json

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.database import Applicant, get_db
from models.schemas import StatusLiteral
from export import generate_csv_export
from dependencies import get_current_admin

router = APIRouter()


def _to_dict(a: Applicant) -> dict:
    """Serialisasi eksplisit -> hindari lazy-load relasi pada sesi async."""
    return {
        "id": a.id,
        "batch_id": a.batch_id,
        "filename": a.filename,
        "applicant_name": a.applicant_name,
        "target_major": a.target_major,
        "skor_kepatuhan": a.skor_kepatuhan,
        "ai_status": a.ai_status,
        "final_status": a.final_status,
        "fraud_flags": json.loads(a.fraud_flags) if a.fraud_flags else [],
        "qr_data": json.loads(a.qr_data) if a.qr_data else [],
        "reasoning": a.reasoning,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/api/applicants")
async def list_applicants(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    result = await db.execute(select(Applicant).order_by(Applicant.id.desc()))
    return {"data": [_to_dict(a) for a in result.scalars().all()]}


@router.get("/api/applicants/export")
async def export_csv(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    csv_buffer = await generate_csv_export(db)
    # \ufeff (BOM) agar Microsoft Excel membaca UTF-8 dengan benar.
    content = "\ufeff" + csv_buffer.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=laporan_pendaftar.csv"},
    )


@router.get("/api/applicants/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    result = await db.execute(select(Applicant))
    applicants = result.scalars().all()

    def has_fraud(a: Applicant) -> bool:
        try:
            return len(json.loads(a.fraud_flags or "[]")) > 0
        except (json.JSONDecodeError, TypeError):
            return False

    return {
        "total": len(applicants),
        "diterima": sum(1 for a in applicants if "diterima" in (a.final_status or "").lower()),
        "ditolak": sum(1 for a in applicants if "ditolak" in (a.final_status or "").lower()),
        "fraud": sum(1 for a in applicants if has_fraud(a)),
    }


@router.post("/api/applicants/{applicant_id}/override")
async def override_status(
    applicant_id: int,
    status: StatusLiteral = Form(...),  # hanya menerima status yang valid
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    result = await db.execute(select(Applicant).where(Applicant.id == applicant_id))
    applicant = result.scalar_one_or_none()
    if not applicant:
        raise HTTPException(404, "Applicant not found")
    applicant.final_status = status
    await db.commit()
    await db.refresh(applicant)
    return {"applicant_id": applicant.id, "final_status": applicant.final_status}
