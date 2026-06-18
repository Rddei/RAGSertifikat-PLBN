import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Applicant
from core.vision import extract_certificate_data
from core.retrieval import retrieve_rules
from core.audit import run_audit
from services.fraud import scan_for_fraud

logger = logging.getLogger("compliance.agent")


async def process_single_application(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    target_major: str,
    expected_name: str,
    db: AsyncSession,
    batch_id: int | None = None,
) -> dict:
    logger.info("Memproses %s (jurusan=%s)", filename, target_major)

    # Stage 0: Fraud detection
    fraud_flags, qr_data = scan_for_fraud(image_bytes)
    # Stage 1: Extraction
    extracted = await extract_certificate_data(image_bytes, content_type)
    # Stage 2: RAG
    rag_context = await retrieve_rules(extracted, target_major)
    # Stage 3: Audit
    audit = await run_audit(
        extracted, target_major, expected_name, fraud_flags, qr_data, rag_context
    )

    # Stage 4: Persist (dengan rollback bila gagal)
    applicant = Applicant(
        batch_id=batch_id,
        filename=filename,
        applicant_name=expected_name,
        target_major=target_major,
        fraud_flags=json.dumps(fraud_flags),
        qr_data=json.dumps(qr_data),
        skor_kepatuhan=audit.get("skor_kepatuhan", 0),
        ai_status=audit.get("status", "Unknown"),
        final_status=audit.get("status", "Unknown"),
        reasoning=audit.get("reasoning", ""),
    )
    db.add(applicant)
    try:
        await db.commit()
        await db.refresh(applicant)
    except Exception:
        await db.rollback()
        logger.exception("Gagal menyimpan applicant untuk file %s", filename)
        raise

    return {
        "metadata": {"filename": filename, "target_major": target_major},
        "security": {"fraud_flags": fraud_flags, "qr_data": qr_data},
        "extraction": extracted,
        "audit": audit,
        "applicant_id": applicant.id,
    }
