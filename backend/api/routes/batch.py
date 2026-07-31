"""
Unggah batch -- MODE UTAMA aplikasi (alur input berbasis nama file).

Verifikator cukup mengunggah file; identitas dan jurusan tujuan di-lookup
dari master pendaftar berdasarkan nama file '<id_pendaftar>-<indeks>.<ext>'
(mis. 221524015-1.pdf). File dengan nama tak sesuai format atau id yang tidak
terdaftar DITOLAK DI AWAL dan dilaporkan pada respons -- tidak ikut diproses.

Kompatibilitas: field form lama (expected_names, jurusan_tujuan) masih
diterima sebagai opsional dan DIABAIKAN, agar frontend lama tidak error
sebelum sempat diperbarui.
"""

import asyncio
import logging
import os
import uuid

from fastapi import (
    APIRouter, Depends, Form, UploadFile, File, BackgroundTasks, HTTPException,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import UPLOAD_DIR
from models.database import get_db, BatchJob, Applicant
from core.agent import process_single_application
from dependencies import get_current_user
from services.pendaftar_service import parse_certificate_filename, get_pendaftar

router = APIRouter()
logger = logging.getLogger("compliance.batch")

# Jeda antar file dalam satu batch (detik) untuk menahan laju permintaan agar
# tidak menembus rate limit (429) Gemini. Tiap sertifikat = beberapa panggilan
# model (Vision + embedding RAG + audit), jadi throttle ini penting di free tier.
# Bisa diatur via env BATCH_ITEM_DELAY_SECONDS (mis. "0" untuk mematikan).
BATCH_ITEM_DELAY = float(os.getenv("BATCH_ITEM_DELAY_SECONDS", "10"))


async def background_batch_processor(batch_id: int, files_info: list):
    from models.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        for idx, f_info in enumerate(files_info):
            # Throttle antar file (dilewati untuk file pertama) agar RPM aman.
            if idx > 0 and BATCH_ITEM_DELAY > 0:
                await asyncio.sleep(BATCH_ITEM_DELAY)
            try:
                with open(f_info["path"], "rb") as f:
                    image_bytes = f.read()
                await process_single_application(
                    image_bytes=image_bytes,
                    filename=f_info["saved_filename"],
                    content_type=f_info["content_type"],
                    target_major=f_info["target_major"],
                    expected_name=f_info["expected_name"],
                    db=db,
                    batch_id=batch_id,
                    id_pendaftaran=f_info["id_pendaftaran"],
                )
            except Exception as e:
                logger.error("Batch error pada %s: %s", f_info.get("saved_filename"), e)

            # Update progress per file (gunakan transaksi terpisah)
            result = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
            job = result.scalar_one_or_none()
            if job:
                job.processed_files += 1
                if job.processed_files >= job.total_files:
                    job.status = "completed"
                await db.commit()


@router.post("/api/audit/batch")
async def process_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    # Field lama: opsional & diabaikan (kompatibilitas frontend lama).
    expected_names: list[str] | None = Form(None),
    jurusan_tujuan: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_user),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    accepted, rejected = [], []

    for uploaded_file in files:
        # os.path.basename mencegah path traversal dari nama file pengguna.
        original = os.path.basename(uploaded_file.filename or "file")

        # 1) Validasi format nama file -> (id_pendaftaran, indeks)
        try:
            id_pendaftaran, indeks = parse_certificate_filename(original)
        except ValueError as exc:
            rejected.append({"filename": original, "alasan": str(exc)})
            continue

        # 2) Lookup master pendaftar; tidak terdaftar -> tolak di awal.
        p = await get_pendaftar(db, id_pendaftaran)
        if p is None:
            rejected.append({
                "filename": original,
                "alasan": (f"Pendaftar tidak tersedia: id '{id_pendaftaran}' "
                           f"tidak ditemukan pada master pendaftar"),
            })
            continue

        safe_filename = f"{uuid.uuid4()}_{original}"
        save_path = os.path.join(UPLOAD_DIR, safe_filename)
        with open(save_path, "wb") as f:
            f.write(await uploaded_file.read())
        accepted.append({
            "path": save_path,
            "filename": original,
            "saved_filename": safe_filename,
            "content_type": uploaded_file.content_type,
            "id_pendaftaran": id_pendaftaran,
            "indeks_sertifikat": indeks,
            "expected_name": p.nama,
            "target_major": p.jurusan_dituju,
        })

    if not accepted:
        raise HTTPException(
            status_code=400,
            detail={"message": "Tidak ada file valid untuk diproses",
                    "rejected": rejected},
        )

    new_batch = BatchJob(total_files=len(accepted), processed_files=0,
                         status="processing")
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)

    background_tasks.add_task(background_batch_processor, new_batch.id, accepted)
    return {
        "message": "Batch started",
        "batch_id": new_batch.id,
        "total_files": len(accepted),
        "accepted": [
            {"filename": a["filename"], "id_pendaftaran": a["id_pendaftaran"],
             "nama": a["expected_name"], "jurusan": a["target_major"]}
            for a in accepted
        ],
        "rejected": rejected,
    }


@router.get("/api/audit/batch/{batch_id}")
async def get_batch_status(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_user),
):
    result = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Batch not found")
    app_result = await db.execute(
        select(Applicant).where(Applicant.batch_id == batch_id)
    )
    return {
        "batch_id": job.id,
        "total": job.total_files,
        "processed": job.processed_files,
        "status": job.status,
        "applicants_processed": len(app_result.scalars().all()),
    }
