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
from dependencies import get_current_admin

router = APIRouter()
logger = logging.getLogger("compliance.batch")


async def background_batch_processor(batch_id: int, files_info: list, target_major: str):
    from models.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        for f_info in files_info:
            try:
                with open(f_info["path"], "rb") as f:
                    image_bytes = f.read()
                await process_single_application(
                    image_bytes=image_bytes,
                    filename=f_info["saved_filename"],
                    content_type=f_info["content_type"],
                    target_major=target_major,
                    expected_name=f_info["expected_name"],
                    db=db,
                    batch_id=batch_id,
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
    expected_names: list[str] = Form(...),
    jurusan_tujuan: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    new_batch = BatchJob(total_files=len(files), processed_files=0, status="processing")
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    files_info = []
    for idx, uploaded_file in enumerate(files):
        # os.path.basename mencegah path traversal dari nama file pengguna.
        original = os.path.basename(uploaded_file.filename or "file")
        safe_filename = f"{uuid.uuid4()}_{original}"
        save_path = os.path.join(UPLOAD_DIR, safe_filename)
        with open(save_path, "wb") as f:
            f.write(await uploaded_file.read())
        files_info.append({
            "path": save_path,
            "filename": original,
            "saved_filename": safe_filename,
            "content_type": uploaded_file.content_type,
            "expected_name": expected_names[idx] if idx < len(expected_names) else "Unknown",
        })

    background_tasks.add_task(
        background_batch_processor, new_batch.id, files_info, jurusan_tujuan
    )
    return {"message": "Batch started", "batch_id": new_batch.id, "total_files": len(files)}


@router.get("/api/audit/batch/{batch_id}")
async def get_batch_status(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
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
