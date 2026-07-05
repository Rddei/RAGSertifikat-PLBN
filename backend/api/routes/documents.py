import logging

from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

# Gunakan AsyncSessionLocal untuk Background Tasks
from models.database import AsyncSessionLocal, User
from services.compliance_service import ComplianceService
from core.genai_utils import ModelUnavailableError
from dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger("compliance.documents")

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "image/webp",
}
# Batas ukuran diturunkan untuk stabilitas produksi (100+ users)
MAX_FILE_SIZE_MB = 5 
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

async def process_document_in_background(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    target_major: str,
    expected_name: str,
    verifikator_id: int, 
):
    """
    Berjalan di latar belakang dengan koneksi basis data mandiri.
    """
    logger.info("Memulai pemrosesan latar belakang untuk file: %s oleh verifikator: %d", filename, verifikator_id)
    async with AsyncSessionLocal() as db_session:
        try:
            await ComplianceService.verify_document(
                image_bytes=image_bytes,
                filename=filename,
                content_type=content_type,
                target_major=target_major,
                expected_name=expected_name,
                db=db_session,
                verifikator_id=verifikator_id
            )
            logger.info("Pemrosesan sukses untuk: %s", filename)
        except Exception as e:
            logger.exception("Gagal memproses file %s di latar belakang", filename)

@router.post("/process-document", status_code=202)
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    expected_name: str = Form(..., min_length=2),
    jurusan_tujuan: str = Form(..., min_length=2),
    current_user: User = Depends(get_current_user), 
):
    # --- Validasi format file ---
    if file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning("Format tidak didukung: %s", file.content_type)
        raise HTTPException(
            status_code=415,
            detail=f"Format file tidak didukung. Gunakan: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    # --- Baca file sambil cek ukuran ---
    image_bytes = await file.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="File kosong tidak dapat diproses")

    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        logger.warning("Ukuran file terlalu besar: %d bytes", len(image_bytes))
        raise HTTPException(
            status_code=413,
            detail=f"Ukuran file melebihi batas maksimum {MAX_FILE_SIZE_MB}MB",
        )

    # --- Delegasikan ke latar belakang agar API tidak timeout ---
    background_tasks.add_task(
        process_document_in_background,
        image_bytes=image_bytes,
        filename=file.filename,
        content_type=file.content_type,
        target_major=jurusan_tujuan,
        expected_name=expected_name,
        verifikator_id=current_user.id
    )

    # Respons seketika ke Next.js
    return {
        "status": "processing",
        "message": f"Dokumen {file.filename} diterima dan sedang diproses di latar belakang.",
        "filename": file.filename
    }