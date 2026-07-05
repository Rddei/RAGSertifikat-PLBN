import logging
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent import process_single_application

logger = logging.getLogger("compliance.service")

class ComplianceService:
    @staticmethod
    async def verify_document(
        image_bytes: bytes,
        filename: str,
        content_type: str,
        target_major: str,
        expected_name: str,
        db: AsyncSession,
        verifikator_id: int = None,
        batch_id: int = None,
    ) -> dict:
        """
        Layanan utama untuk menjembatani rute dokumen dengan core agent.
        """
        logger.info("ComplianceService menerima dokumen: %s", filename)
        
        # Panggil agen AI untuk memproses ekstraksi, RAG, dan Audit
        # dan meneruskan verifikator_id untuk disimpan ke database
        result = await process_single_application(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
            target_major=target_major,
            expected_name=expected_name,
            db=db,
            batch_id=batch_id,
            verifikator_id=verifikator_id
        )
        
        return result