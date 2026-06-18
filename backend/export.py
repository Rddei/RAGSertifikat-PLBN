import csv
import io
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.database import Applicant

logger = logging.getLogger("compliance.export")


def _format_fraud_flags(raw: str | None) -> str:
    """Ubah fraud_flags (string JSON) menjadi teks yang mudah dibaca."""
    if not raw:
        return ""
    try:
        flags = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if isinstance(flags, list):
        return "; ".join(str(f) for f in flags)
    return str(flags)


async def generate_csv_export(db: AsyncSession) -> io.StringIO:
    """Ekspor seluruh pendaftar ke buffer CSV (StringIO)."""
    result = await db.execute(select(Applicant).order_by(Applicant.id.desc()))
    applicants = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "Nama Pendaftar", "Jurusan", "Nama File",
        "Skor Kepatuhan", "Status AI", "Status Final",
        "Fraud Flags", "Reasoning", "Tanggal",
    ])

    for a in applicants:
        writer.writerow([
            a.id,
            a.applicant_name or "",
            a.target_major or "",
            a.filename or "",
            a.skor_kepatuhan if a.skor_kepatuhan is not None else "",
            a.ai_status or "",
            a.final_status or "",
            _format_fraud_flags(a.fraud_flags),
            a.reasoning or "",
            a.created_at.isoformat() if a.created_at else "",
        ])

    output.seek(0)
    return output
