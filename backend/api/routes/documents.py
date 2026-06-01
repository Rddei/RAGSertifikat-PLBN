import uuid
import logging
from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import get_db
from services.compliance_service import ComplianceService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/process-document")
async def process_document(
    file: UploadFile = File(...),
    expected_name: str = Form(..., min_length=2),
    jurusan_tujuan: str = Form(..., min_length=2),
    db: AsyncSession = Depends(get_db)
):
    # Baca file tanpa menyimpan permanen di sini (service bisa handle jika perlu)
    image_bytes = await file.read()
    
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
        logger.error("AI pipeline error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal error") from e