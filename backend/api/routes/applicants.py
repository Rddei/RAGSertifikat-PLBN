import json

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Import User juga untuk typing
from models.database import Applicant, get_db, User
from models.schemas import StatusLiteral
from export import generate_csv_export, generate_xlsx_export
# Ganti import menjadi get_current_user
from dependencies import get_current_user

router = APIRouter()


def _to_dict(a: Applicant) -> dict:
    """Serialisasi eksplisit -> hindari lazy-load relasi pada sesi async."""
    return {
        "id": a.id,
        "batch_id": a.batch_id,
        "filename": a.filename,
        "applicant_name": a.applicant_name,
        "target_major": a.target_major,
        # --- Hasil ekstraksi sertifikat ---
        "nama_peserta": a.nama_peserta,
        "nama_lomba": a.nama_lomba,
        "singkatan_lomba": a.singkatan_lomba,
        "nama_penyelenggara": a.nama_penyelenggara,
        "kategori": a.kategori,
        "tingkat": a.tingkat,
        "tanggal_kegiatan": a.tanggal_kegiatan,
        "peringkat": a.peringkat,
        "nomor_sertifikat": a.nomor_sertifikat,
        "url_verifikasi": a.url_verifikasi,
        "penandatangan": a.penandatangan,
        "ada_cap": a.ada_cap,
        "deskripsi_cap": a.deskripsi_cap,
        "ada_ttd": a.ada_ttd,
        # --- Keamanan & audit ---
        "skor_kepatuhan": a.skor_kepatuhan,
        "ai_status": a.ai_status,
        "final_status": a.final_status,
        # --- Kurasi SIMT ---
        "kurasi_status": a.kurasi_status,
        "kurasi_skor_nama": a.kurasi_skor_nama,
        "kurasi_skor_penyelenggara": a.kurasi_skor_penyelenggara,
        "kurasi_ajang_terdekat": a.kurasi_ajang_terdekat,
        "fraud_flags": json.loads(a.fraud_flags) if a.fraud_flags else [],
        "qr_data": json.loads(a.qr_data) if a.qr_data else [],
        "reasoning": a.reasoning,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "verifikator_id": a.verifikator_id,
    }


@router.get("/api/applicants")
async def list_applicants(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # LOGIKA RBAC: Filter Isolasi Data
    if current_user.role == "admin":
        query = select(Applicant).order_by(Applicant.id.desc())
    else:
        query = select(Applicant).where(Applicant.verifikator_id == current_user.id).order_by(Applicant.id.desc())

    result = await db.execute(query)
    return {"data": [_to_dict(a) for a in result.scalars().all()]}


@router.get("/api/applicants/export")
async def export_report(
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Proteksi: Fitur export laporan HANYA untuk Admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Hanya Admin yang diizinkan mengunduh laporan.")

    fmt = (format or "csv").lower()

    if fmt == "xlsx":
        try:
            xlsx_buffer = await generate_xlsx_export(db)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return StreamingResponse(
            iter([xlsx_buffer.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=laporan_pendaftar.xlsx"},
        )

    # Default: CSV (dengan BOM agar Excel membaca UTF-8 dengan benar)
    csv_buffer = await generate_csv_export(db)
    content = "\ufeff" + csv_buffer.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=laporan_pendaftar.csv"},
    )


@router.get("/api/applicants/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # LOGIKA RBAC untuk Metrik
    if current_user.role == "admin":
        query = select(Applicant)
    else:
        query = select(Applicant).where(Applicant.verifikator_id == current_user.id)

    result = await db.execute(query)
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
    status: StatusLiteral = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Cek hak akses ke dokumen ini
    if current_user.role == "admin":
        query = select(Applicant).where(Applicant.id == applicant_id)
    else:
        query = select(Applicant).where(
            Applicant.id == applicant_id,
            Applicant.verifikator_id == current_user.id
        )

    result = await db.execute(query)
    applicant = result.scalar_one_or_none()

    if not applicant:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan atau Anda tidak memiliki akses.")

    applicant.final_status = status
    await db.commit()
    await db.refresh(applicant)

    return {"applicant_id": applicant.id, "final_status": applicant.final_status}
