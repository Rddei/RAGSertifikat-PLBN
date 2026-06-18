import logging
from typing import Any

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
        batch_id: int | None = None,
    ) -> dict[str, Any]:
        """Menjalankan pipeline penuh dan mengembalikan hasil."""
        logger.info(
            "Mulai verifikasi dokumen: %s (jurusan=%s)", filename, target_major
        )
        return await process_single_application(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
            target_major=target_major,
            expected_name=expected_name,
            db=db,
            batch_id=batch_id,
        )
