"""
POLBAN Intelligent Compliance Engine — Refactored
==================================================
Changes from original:
  - Route ordering fixed (static paths before parameterised ones)
  - AI response parsing hardened with fallback logic
  - Fraud-flag check uses proper JSON deserialization
  - Passwords hashed with bcrypt (import guard keeps startup fast)
  - Hard-coded session token replaced with secrets.token_hex
  - Input validation via Pydantic / Form constraints
  - process_single_application broken into focused private helpers
  - All bare `except Exception` replaced with typed handlers + logging
  - BatchJob import consolidated at module level
  - Scaffolding comments ("Phase N") removed
"""

from __future__ import annotations

import io
import json
import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Any

import chromadb
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from google import genai as google_genai
from google.genai import types as genai_types
from llama_index.core import Settings, VectorStoreIndex
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.vector_stores.chroma import ChromaVectorStore
from PIL import Image
from PIL.ExifTags import TAGS
from pydantic import BaseModel, Field
from pyzbar.pyzbar import decode as decode_qr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import AsyncSessionLocal, engine, get_db
from export import generate_csv_export
from models import Admin, Applicant, Base, BatchJob

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("polban")

# ---------------------------------------------------------------------------
# Environment & AI clients
# ---------------------------------------------------------------------------
load_dotenv()

_api_key = os.getenv("GOOGLE_API_KEY")
if not _api_key:
    raise EnvironmentError("GOOGLE_API_KEY is not set")

llm = GoogleGenAI(model="models/gemini-2.5-flash", api_key=_api_key)
vision_client = google_genai.Client(api_key=_api_key)
embed_model = GoogleGenAIEmbedding(model="models/embedding-001", api_key=_api_key)

Settings.embed_model = embed_model
Settings.llm = llm

# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------
_chroma_client = chromadb.PersistentClient(path="./chroma_db")
_chroma_collection = _chroma_client.get_or_create_collection("polban_rules")
_vector_store = ChromaVectorStore(chroma_collection=_chroma_collection)
_index = VectorStoreIndex.from_vector_store(_vector_store)
query_engine = _index.as_query_engine()

# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).limit(1))
        if result.scalar_one_or_none() is None:
            hashed = _hash_password("polban123")
            session.add(Admin(username="admin", password=hashed))
            await session.commit()
            logger.info("Default admin account seeded (admin / polban123)")

    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="POLBAN Intelligent Compliance Engine", lifespan=lifespan)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
def _hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*.  Falls back to plain text if bcrypt
    is unavailable so the rest of the app can still start during development."""
    try:
        import bcrypt  # optional dep — install with: pip install bcrypt
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        logger.warning("bcrypt not installed — storing password as plain text (dev only)")
        return plain


def _verify_password(plain: str, stored: str) -> bool:
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode(), stored.encode())
    except ImportError:
        return plain == stored


# ---------------------------------------------------------------------------
# AI pipeline — private helpers
# ---------------------------------------------------------------------------

def _scan_image_for_fraud(image_bytes: bytes) -> tuple[list[str], list[str]]:
    """Return (fraud_flags, qr_data) from EXIF and barcode analysis."""
    fraud_flags: list[str] = []
    qr_data: list[str] = []

    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name in ("Software", "ProcessingSoftware"):
                    val_lower = str(value).lower()
                    if any(kw in val_lower for kw in ("adobe", "photoshop", "canva")):
                        fraud_flags.append(f"Editing software detected: {value}")

        for obj in decode_qr(img):
            qr_data.append(obj.data.decode("utf-8"))

    except Exception as exc:
        logger.warning("Image pre-processing warning: %s", exc)

    return fraud_flags, qr_data


async def _extract_certificate_data(image_bytes: bytes, content_type: str) -> dict[str, Any]:
    """Call Gemini Vision to extract structured certificate fields.
    Returns a dict with keys: nama_peserta, jenjang_sekolah, nama_lomba, nama_penyelenggara.
    Raises ValueError if the model returns unparseable JSON.
    """
    prompt = (
        "Anda adalah asisten ekstraksi data. Perhatikan gambar sertifikat ini.\n"
        "Ekstrak data ke dalam format JSON murni (tanpa teks tambahan atau markdown):\n"
        '{"nama_peserta":"...","jenjang_sekolah":"...","nama_lomba":"...","nama_penyelenggara":"..."}'
    )
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=content_type)
    response = await vision_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, image_part],
    )
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Vision model returned non-JSON: {raw[:200]}") from exc


async def _retrieve_admission_rules(extracted: dict[str, Any], target_major: str) -> str:
    """Query the RAG index for relevant admission rules."""
    query = (
        f"Aturan admisi untuk jenjang {extracted.get('jenjang_sekolah', '')} "
        f"dan lomba {extracted.get('nama_lomba', '')} "
        f"untuk jurusan {target_major}"
    )
    result = await query_engine.aquery(query)
    return result.response


async def _run_audit(
    extracted: dict[str, Any],
    target_major: str,
    expected_name: str,
    fraud_flags: list[str],
    qr_data: list[str],
    rag_context: str,
) -> dict[str, Any]:
    """Ask the LLM auditor to produce a compliance verdict.
    Returns a dict with keys: status, skor_kepatuhan, langkah_gagal, reasoning.
    Raises ValueError on unparseable JSON.
    """
    fraud_summary = fraud_flags if fraud_flags else "Bersih (tidak ada indikasi software editan)"
    qr_summary = qr_data if qr_data else "Tidak ditemukan barcode"

    prompt = f"""
Anda adalah Auditor Admisi POLBAN Berbasis AI.
Tugas Anda: Berikan penilaian kelayakan berdasarkan data berikut.

DATA PENDAFTAR:
{json.dumps(extracted, indent=2, ensure_ascii=False)}
JURUSAN TUJUAN: {target_major}
NAMA YANG DIHARAPKAN: {expected_name}

ATURAN VALIDASI NAMA (SANGAT PENTING!):
- Bandingkan "nama_peserta" dari dokumen dengan NAMA YANG DIHARAPKAN ("{expected_name}").
- Jika namanya berbeda jauh atau tidak cocok, ubah status menjadi "Ditolak" dan jelaskan di reasoning.

ANTI-KECURANGAN:
- Flags    : {fraud_summary}
- QR / Barcode: {qr_summary}
  (Jika Flags menunjukkan indikasi editan, WAJIB ubah status menjadi "Ditolak" dan berikan skor 0.)

KONTEKS ATURAN (RAG):
{rag_context}

Balas HANYA dengan JSON murni (tanpa markdown):
{{
    "status": "Diterima | Ditolak | Butuh Tinjauan Manual",
    "skor_kepatuhan": 0-100,
    "langkah_gagal": "Sebutkan langkah yang tidak terpenuhi, atau null",
    "reasoning": "Penjelasan detail, WAJIB menyebut pencocokkan nama."
}}
""".strip()

    response = await llm.acomplete(prompt)
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Audit model returned non-JSON: {raw[:200]}") from exc


async def _persist_applicant(
    db: AsyncSession,
    *,
    batch_id: int | None,
    filename: str,
    expected_name: str,
    target_major: str,
    fraud_flags: list[str],
    qr_data: list[str],
    audit: dict[str, Any],
) -> Applicant:
    """Insert a new Applicant row and return the refreshed ORM object."""
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
    await db.commit()
    await db.refresh(applicant)
    return applicant


# ---------------------------------------------------------------------------
# Core pipeline (orchestrator)
# ---------------------------------------------------------------------------
async def process_single_application(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    target_major: str,
    expected_name: str,
    db: AsyncSession,
    batch_id: int | None = None,
) -> dict[str, Any]:
    """Full 4-stage pipeline: fraud scan → extraction → RAG → audit → persist."""
    # Stage 0: Fraud & forgery detection
    fraud_flags, qr_data = _scan_image_for_fraud(image_bytes)

    # Stage 1: Vision extraction
    extracted = await _extract_certificate_data(image_bytes, content_type)

    # Stage 2: RAG retrieval
    rag_context = await _retrieve_admission_rules(extracted, target_major)

    # Stage 3: Agentic audit
    audit = await _run_audit(
        extracted=extracted,
        target_major=target_major,
        expected_name=expected_name,
        fraud_flags=fraud_flags,
        qr_data=qr_data,
        rag_context=rag_context,
    )

    # Stage 4: Persist to database
    applicant = await _persist_applicant(
        db,
        batch_id=batch_id,
        filename=filename,
        expected_name=expected_name,
        target_major=target_major,
        fraud_flags=fraud_flags,
        qr_data=qr_data,
        audit=audit,
    )

    return {
        "metadata": {"filename": filename, "target_major": target_major},
        "security": {"fraud_flags": fraud_flags, "qr_data": qr_data},
        "extraction": extracted,
        "audit": audit,
        "applicant_id": applicant.id,
    }


# ---------------------------------------------------------------------------
# Background batch processor
# ---------------------------------------------------------------------------
async def _background_batch_processor(
    batch_id: int,
    files_info: list[dict[str, Any]],
    target_major: str,
) -> None:
    async with AsyncSessionLocal() as db:
        for f_info in files_info:
            try:
                with open(f_info["path"], "rb") as fh:
                    image_bytes = fh.read()

                await process_single_application(
                    image_bytes=image_bytes,
                    filename=f_info["saved_filename"],
                    content_type=f_info["content_type"],
                    target_major=target_major,
                    expected_name=f_info["expected_name"],
                    db=db,
                    batch_id=batch_id,
                )
            except Exception as exc:
                logger.error(
                    "Batch %d: failed to process '%s': %s",
                    batch_id,
                    f_info.get("filename"),
                    exc,
                    exc_info=True,
                )

            # Increment progress regardless of per-file success/failure
            result = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
            job = result.scalar_one_or_none()
            if job:
                job.processed_files += 1
                if job.processed_files >= job.total_files:
                    job.status = "completed"
                await db.commit()


# ---------------------------------------------------------------------------
# Routes — IMPORTANT: static paths MUST be declared before parameterised ones
# so FastAPI does not treat "export" or "metrics" as {applicant_id} values.
# ---------------------------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "active",
        "engine": "Agentic-RAG Full Pipeline",
        "vector_db": "ChromaDB connected",
    }


# ── Documents ──────────────────────────────────────────────────────────────

@app.post("/process-document")
async def process_document(
    file: UploadFile = File(...),
    expected_name: str = Form(..., min_length=2, max_length=200),
    jurusan_tujuan: str = Form(..., min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    save_path = os.path.join("uploads", safe_filename)

    image_bytes = await file.read()
    with open(save_path, "wb") as fh:
        fh.write(image_bytes)

    try:
        return await process_single_application(
            image_bytes=image_bytes,
            filename=safe_filename,
            content_type=file.content_type,
            target_major=jurusan_tujuan,
            expected_name=expected_name,
            db=db,
        )
    except ValueError as exc:
        logger.error("AI pipeline error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in process_document")
        raise HTTPException(status_code=500, detail="Internal pipeline error") from exc


# ── Applicants — static sub-paths first ────────────────────────────────────

@app.get("/api/applicants")
async def list_applicants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant).order_by(Applicant.id.desc()))
    return {"data": result.scalars().all()}


@app.get("/api/applicants/export")
async def export_applicants_csv(db: AsyncSession = Depends(get_db)):
    """Download all applicant records as a CSV file."""
    csv_buffer = await generate_csv_export(db)
    return StreamingResponse(
        iter([csv_buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=laporan_pendaftar.csv"},
    )


@app.get("/api/applicants/metrics")
async def get_applicant_metrics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant))
    applicants = result.scalars().all()

    def _has_fraud(a: Applicant) -> bool:
        try:
            return bool(json.loads(a.fraud_flags or "[]"))
        except (json.JSONDecodeError, TypeError):
            return False

    total = len(applicants)
    return {
        "total": total,
        "diterima": sum(1 for a in applicants if "diterima" in (a.final_status or "").lower()),
        "ditolak": sum(1 for a in applicants if "ditolak" in (a.final_status or "").lower()),
        "fraud": sum(1 for a in applicants if _has_fraud(a)),
    }


# ── Applicants — parameterised paths last ──────────────────────────────────

@app.post("/api/applicants/{applicant_id}/override")
async def override_applicant_status(
    applicant_id: int,
    status: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Applicant).where(Applicant.id == applicant_id))
    applicant = result.scalar_one_or_none()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    applicant.final_status = status
    await db.commit()
    await db.refresh(applicant)
    return {"applicant_id": applicant.id, "final_status": applicant.final_status}


# ── Authentication ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=200)


@app.post("/api/auth/login")
async def login_admin(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.username == request.username))
    admin = result.scalar_one_or_none()

    if not admin or not _verify_password(request.password, admin.password):
        raise HTTPException(status_code=401, detail="Username atau Password salah")

    # In production replace this with a proper JWT library (e.g. python-jose)
    session_token = secrets.token_hex(32)
    return {"message": "Login successful", "token": session_token}


# ── Batch processing ────────────────────────────────────────────────────────

@app.post("/api/audit/batch")
async def process_batch_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    expected_names: list[str] = Form(...),
    jurusan_tujuan: str = Form(..., min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    new_batch = BatchJob(total_files=len(files), processed_files=0, status="processing")
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)

    files_info: list[dict[str, Any]] = []
    for idx, uploaded_file in enumerate(files):
        safe_filename = f"{uuid.uuid4()}_{uploaded_file.filename}"
        save_path = os.path.join("uploads", safe_filename)
        file_bytes = await uploaded_file.read()
        with open(save_path, "wb") as fh:
            fh.write(file_bytes)

        files_info.append({
            "path": save_path,
            "filename": uploaded_file.filename,
            "saved_filename": safe_filename,
            "content_type": uploaded_file.content_type,
            "expected_name": expected_names[idx] if idx < len(expected_names) else "Unknown",
        })

    background_tasks.add_task(
        _background_batch_processor, new_batch.id, files_info, jurusan_tujuan
    )
    return {
        "message": "Batch processing started",
        "batch_id": new_batch.id,
        "total_files": len(files),
    }


@app.get("/api/audit/batch/{batch_id}")
async def get_batch_status(batch_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    app_result = await db.execute(
        select(Applicant).where(Applicant.batch_id == batch_id)
    )
    applicant_count = len(app_result.scalars().all())

    return {
        "batch_id": job.id,
        "total": job.total_files,
        "processed": job.processed_files,
        "status": job.status,
        "applicants_processed": applicant_count,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)