# export.py
import csv
import io
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.database import Applicant

async def generate_csv_export(db: AsyncSession):
    """Export all applicants to a CSV file."""
    result = await db.execute(select(Applicant).order_by(Applicant.id.desc()))
    applicants = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Nama Pendaftar", "Jurusan", "Nama File",
        "Skor Kepatuhan", "Status AI", "Status Final",
        "Fraud Flags", "Reasoning", "Tanggal"
    ])

    # Data
    for a in applicants:
        writer.writerow([
            a.id,
            a.applicant_name,
            a.target_major,
            a.filename,
            a.skor_kepatuhan,
            a.ai_status,
            a.final_status,
            a.fraud_flags,
            a.reasoning,
            a.created_at.isoformat() if a.created_at else ""
        ])

    output.seek(0)
    return output