from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.database import Applicant, get_db
from export import generate_csv_export
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/api/applicants")
async def list_applicants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant).order_by(Applicant.id.desc()))
    return {"data": result.scalars().all()}

@router.get("/api/applicants/export")
async def export_csv(db: AsyncSession = Depends(get_db)):
    csv_buffer = await generate_csv_export(db)
    return StreamingResponse(
        iter([csv_buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=laporan_pendaftar.csv"}
    )

@router.get("/api/applicants/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant))
    applicants = result.scalars().all()
    def has_fraud(a: Applicant):
        try:
            import json
            return len(json.loads(a.fraud_flags or "[]")) > 0
        except:
            return False
    total = len(applicants)
    return {
        "total": total,
        "diterima": sum(1 for a in applicants if "diterima" in (a.final_status or "").lower()),
        "ditolak": sum(1 for a in applicants if "ditolak" in (a.final_status or "").lower()),
        "fraud": sum(1 for a in applicants if has_fraud(a))
    }

@router.post("/api/applicants/{applicant_id}/override")
async def override_status(applicant_id: int, status: str = Form(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant).where(Applicant.id == applicant_id))
    applicant = result.scalar_one_or_none()
    if not applicant:
        raise HTTPException(404, "Applicant not found")
    applicant.final_status = status
    await db.commit()
    await db.refresh(applicant)
    return {"applicant_id": applicant.id, "final_status": applicant.final_status}