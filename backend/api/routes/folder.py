"""
Impor batch dari FOLDER di server -- FITUR TAMBAHAN (terpisah dari alur unggah).

Endpoint ini membaca berkas sertifikat yang sudah ada pada sebuah folder di
server, lalu memprosesnya memakai pipeline yang SAMA dengan alur unggah batch
(lookup master pendaftar berdasarkan nama file, lalu process_single_application).

Dibuat terpisah agar tidak mengubah alur unggah batch yang sudah stabil. Semua
fungsi inti (parse nama, lookup pendaftar, pemroses background) dipakai ulang
dari modul yang sudah ada -- tidak ada logika pemrosesan yang diduplikasi.

Keamanan:
- Folder yang boleh dibaca dibatasi ke root yang di-whitelist lewat env
  FOLDER_INGEST_ROOT (default: subfolder 'folder_ingest' di UPLOAD_DIR).
- Path hasil gabungan divalidasi agar tetap di dalam root (cegah path traversal
  seperti '../../etc').
- Endpoint tetap memerlukan autentikasi (get_current_user), sama seperti batch.
"""

import logging
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import UPLOAD_DIR
from models.database import get_db, BatchJob
from dependencies import get_current_user
from services.pendaftar_service import parse_certificate_filename, get_pendaftar

# Dipakai ulang dari alur batch -- TIDAK didefinisikan ulang di sini.
from api.routes.batch import background_batch_processor

router = APIRouter()
logger = logging.getLogger("compliance.folder")

# Root folder yang boleh dibaca. Semua path folder yang diminta harus berada di
# dalam root ini. Default: subfolder 'folder_ingest' di dalam UPLOAD_DIR.
FOLDER_INGEST_ROOT = os.getenv(
    "FOLDER_INGEST_ROOT", os.path.join(UPLOAD_DIR, "folder_ingest")
)

# Ekstensi berkas yang diterima (samakan dengan batasan sistem).
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


class FolderIngestRequest(BaseModel):
    # Subpath relatif terhadap FOLDER_INGEST_ROOT. Kosong = root itu sendiri.
    subfolder: str = ""


def _resolve_safe_folder(subfolder: str) -> str:
    """Gabungkan subfolder ke root dan pastikan hasilnya tetap di dalam root."""
    root = os.path.realpath(FOLDER_INGEST_ROOT)
    target = os.path.realpath(os.path.join(root, subfolder))
    # Cegah path traversal: target harus berada di dalam root.
    if target != root and not target.startswith(root + os.sep):
        raise HTTPException(
            status_code=400,
            detail="Folder di luar area yang diizinkan.",
        )
    if not os.path.isdir(target):
        raise HTTPException(
            status_code=404,
            detail=f"Folder tidak ditemukan: {subfolder or '(root)'}",
        )
    return target


@router.post("/api/audit/folder")
async def process_folder(
    payload: FolderIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_user),
):
    """
    Baca berkas dari folder server, lookup pendaftar dari nama file, lalu proses
    dengan pipeline batch yang sama. Mengembalikan daftar accepted/rejected dan
    batch_id untuk dipantau lewat endpoint status batch yang sudah ada.
    """
    folder = _resolve_safe_folder(payload.subfolder)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    accepted, rejected = [], []

    # Daftar berkas pada folder (tidak rekursif -- hanya level teratas).
    try:
        entries = sorted(os.listdir(folder))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Gagal membaca folder: {exc}")

    for name in entries:
        src_path = os.path.join(folder, name)
        if not os.path.isfile(src_path):
            continue

        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED_EXT:
            rejected.append({"filename": name, "alasan": f"Ekstensi tidak didukung: {ext}"})
            continue

        # 1) Validasi format nama file -> (id_pendaftaran, indeks). Sama spt batch.
        try:
            id_pendaftaran, indeks = parse_certificate_filename(name)
        except ValueError as exc:
            rejected.append({"filename": name, "alasan": str(exc)})
            continue

        # 2) Lookup master pendaftar; tidak terdaftar -> tolak di awal.
        p = await get_pendaftar(db, id_pendaftaran)
        if p is None:
            rejected.append({
                "filename": name,
                "alasan": (f"Pendaftar tidak tersedia: id '{id_pendaftaran}' "
                           f"tidak ditemukan pada master pendaftar"),
            })
            continue

        # Salin berkas ke UPLOAD_DIR (folder sumber tidak diubah/dihapus).
        safe_filename = f"{uuid.uuid4()}_{name}"
        save_path = os.path.join(UPLOAD_DIR, safe_filename)
        try:
            shutil.copyfile(src_path, save_path)
        except OSError as exc:
            rejected.append({"filename": name, "alasan": f"Gagal menyalin berkas: {exc}"})
            continue

        # Tebak content_type dari ekstensi (folder tak menyediakannya).
        content_type = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".pdf": "application/pdf",
        }.get(ext, "application/octet-stream")

        accepted.append({
            "path": save_path,
            "filename": name,
            "saved_filename": safe_filename,
            "content_type": content_type,
            "id_pendaftaran": id_pendaftaran,
            "indeks_sertifikat": indeks,
            "expected_name": p.nama,
            "target_major": p.jurusan_dituju,
        })

    if not accepted:
        raise HTTPException(
            status_code=400,
            detail={"message": "Tidak ada file valid untuk diproses dari folder",
                    "rejected": rejected},
        )

    # Buat batch job & jalankan pemroses background yang SAMA dengan alur unggah.
    new_batch = BatchJob(total_files=len(accepted), processed_files=0,
                         status="processing")
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)

    background_tasks.add_task(background_batch_processor, new_batch.id, accepted)
    return {
        "message": "Folder ingest started",
        "source_folder": payload.subfolder or "(root)",
        "batch_id": new_batch.id,
        "total_files": len(accepted),
        "accepted": [
            {"filename": a["filename"], "id_pendaftaran": a["id_pendaftaran"],
             "nama": a["expected_name"], "jurusan": a["target_major"]}
            for a in accepted
        ],
        "rejected": rejected,
    }