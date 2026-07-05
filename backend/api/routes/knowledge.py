import os
import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from dependencies import get_current_user
from models.database import User
# Asumsi fungsi utama di indexer Anda bernama run_indexer (sesuaikan jika berbeda)
# Jika indexer Anda berupa script terpisah, kita bisa menggunakan subprocess
import subprocess

router = APIRouter()
logger = logging.getLogger("compliance.knowledge")

# Tentukan path file markdown knowledge base
# Sesuaikan jika struktur folder Anda berbeda
KB_FILE_PATH = os.path.join(os.getcwd(), "knowledge_base", "data", "kriteria_snbp_polban_2026.md")

class KBContent(BaseModel):
    content: str


def run_indexer_in_background():
    """Menjalankan proses ingest/indexing ke ChromaDB di latar belakang."""
    logger.info("Memulai proses indexing Knowledge Base (ChromaDB)...")
    try:
        # Menjalankan skrip indexer.py menggunakan subprocess
        # Pastikan path 'knowledge_base/indexer.py' sesuai dengan letak file Anda
        indexer_script = os.path.join(os.getcwd(), "knowledge_base", "indexer.py")
        result = subprocess.run(
            ["python", indexer_script], 
            capture_output=True, 
            text=True, 
            check=True
        )
        logger.info("Indexing selesai dengan sukses: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("Gagal melakukan indexing: %s", e.stderr)
    except Exception as e:
        logger.exception("Terjadi kesalahan tak terduga saat indexing")


@router.get("/api/kb/content")
async def get_knowledge_base_content(
    current_user: User = Depends(get_current_user),
):
    """Membaca isi file markdown untuk ditampilkan di editor UI Admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Hanya Admin yang dapat mengakses setelan aturan.")

    if not os.path.exists(KB_FILE_PATH):
        raise HTTPException(status_code=404, detail="File Knowledge Base tidak ditemukan di server.")

    try:
        with open(KB_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "content": content}
    except Exception as e:
        logger.exception("Gagal membaca file KB")
        raise HTTPException(status_code=500, detail="Gagal membaca file rules") from e


@router.put("/api/kb/content")
async def update_knowledge_base_content(
    payload: KBContent,
    current_user: User = Depends(get_current_user),
):
    """Menyimpan hasil edit markdown dari UI Admin kembali ke file."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Hanya Admin yang dapat mengubah aturan.")

    try:
        # Buat direktori jika belum ada (safety check)
        os.makedirs(os.path.dirname(KB_FILE_PATH), exist_ok=True)
        
        with open(KB_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(payload.content)
            
        logger.info("Admin '%s' telah memperbarui file Knowledge Base.", current_user.username)
        return {"status": "success", "message": "File Knowledge Base berhasil diperbarui."}
    except Exception as e:
        logger.exception("Gagal menulis file KB")
        raise HTTPException(status_code=500, detail="Gagal menyimpan perubahan aturan") from e


@router.post("/api/kb/ingest", status_code=202)
async def trigger_ingest(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Memicu pembaruan ChromaDB (vektor) dari file markdown terbaru."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Hanya Admin yang dapat memicu sinkronisasi AI.")

    # Serahkan tugas berat ke latar belakang
    background_tasks.add_task(run_indexer_in_background)

    return {
        "status": "processing",
        "message": "Proses sinkronisasi aturan ke AI sedang berjalan di latar belakang. Proses ini memakan waktu beberapa saat."
    }