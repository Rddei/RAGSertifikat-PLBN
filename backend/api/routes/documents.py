import uuid
import logging
from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import get_db
from services.compliance_service import ComplianceService

router = APIRouter()
logger = logging.getLogger(__name__)

# Konfigurasi yang diizinkan
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "image/webp",
}
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

@router.post("/process-document")
async def process_document(
    file: UploadFile = File(...),
    expected_name: str = Form(..., min_length=2),
    jurusan_tujuan: str = Form(..., min_length=2),
    db: AsyncSession = Depends(get_db)
):
    # --- Validasi format file ---
    if file.content_type not in ALLOWED_MIME_TYPES:
        print(f"WARNING: Format tidak didukung: {file.content_type}")
        logger.warning("Format tidak didukung: %s", file.content_type)
        raise HTTPException(
            status_code=415,
            detail=f"Format file tidak didukung. Gunakan: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    # --- Baca file sambil cek ukuran ---
    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        print(f"WARNING: Ukuran file terlalu besar: {len(image_bytes)} bytes")
        logger.warning("Ukuran file terlalu besar: %d bytes", len(image_bytes))
        raise HTTPException(
            status_code=413,
            detail=f"Ukuran file melebihi batas maksimum {MAX_FILE_SIZE_MB}MB"
        )

    if len(image_bytes) == 0:
        print("ERROR: File kosong")
        raise HTTPException(status_code=400, detail="File kosong tidak dapat diproses")

    # --- Jalankan pipeline ---
    try:
        result = await ComplianceService.verify_document(
            image_bytes=image_bytes,
            filename=file.filename,
            content_type=file.content_type,
            target_major=jurusan_tujuan,
            expected_name=expected_name,
            db=db
        )
        return result
    except ValueError as e:
        print(f"ERROR (ValueError): {str(e)}")
        logger.error("AI pipeline error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        print(f"ERROR (Exception): {str(e)}")
        logger.exception("Unexpected error in pipeline")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan internal saat memproses dokumen") from e