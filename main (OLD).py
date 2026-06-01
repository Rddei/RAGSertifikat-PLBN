# nest_asyncio dihapus — gunakan async/await native FastAPI

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import io
import json
import chromadb
from PIL import Image
from PIL.ExifTags import TAGS
from pyzbar.pyzbar import decode as decode_qr
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex, Settings
from google import genai as google_genai
from google.genai import types as genai_types

# Database imports
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import engine, get_db
from models import Applicant, Base

# 1. Load Environment Variables
load_dotenv()

# 2. Setup AI Models Configuration
llm = GoogleGenAI(
    model="models/gemini-2.5-flash", 
    api_key=os.getenv("GOOGLE_API_KEY")
)

# Vision client pakai google.genai (baru) — support async native
vision_client = google_genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

embed_model = GoogleGenAIEmbedding(
    model="models/embedding-001", 
    api_key=os.getenv("GOOGLE_API_KEY")
)

Settings.embed_model = embed_model
Settings.llm = llm

# 3. Setup Vector Database (ChromaDB)
db = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = db.get_or_create_collection("polban_rules")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
index = VectorStoreIndex.from_vector_store(vector_store)
query_engine = index.as_query_engine()

# Inisialisasi Database SQLite (Async) menggunakan Lifespan Events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    async with engine.begin() as conn:
        import models
        await conn.run_sync(models.Base.metadata.create_all)
        
    # Check for admin user and seed if not present
    from models import Admin
    from sqlalchemy.future import select
    from database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).limit(1))
        existing_admin = result.scalar_one_or_none()
        
        if not existing_admin:
            # Seed default admin
            default_admin = Admin(username="admin", password="polban123")
            session.add(default_admin)
            await session.commit()
            print("INFO:     Default admin account seeded (admin:polban123)")

    yield
    # --- Shutdown ---
    pass

app = FastAPI(title="POLBAN Intelligent Compliance Engine", lifespan=lifespan)

# Buka akses folder uploads as static files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "Active", 
        "engine": "Agentic-RAG Full Pipeline",
        "database": "ChromaDB Connected"
    }

# 5. MASTER ENDPOINT: AUTOMATED VISION + RAG PIPELINE
async def process_single_application(
    image_bytes: bytes, 
    filename: str, 
    content_type: str, 
    jurusan_tujuan: str, 
    expected_name: str,
    db: AsyncSession, 
    batch_id: int = None
):
    # --- STAGE 0: FRAUD & FORGERY DETECTION ---
    fraud_flags = []
    qr_data = []
    
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        
        # 0A: EXIF Metadata Analysis
        exif_data = pil_img.getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "Software" or tag_name == "ProcessingSoftware":
                    val_str = str(value).lower()
                    if "adobe" in val_str or "photoshop" in val_str or "canva" in val_str:
                        fraud_flags.append(f"Terindikasi editan software: {value}")
        
        # 0B: QR / Barcode Scanning
        decoded_objects = decode_qr(pil_img)
        for obj in decoded_objects:
            qr_data.append(obj.data.decode("utf-8"))
            
    except Exception as e:
        print(f"Vision pre-processing warning: {str(e)}")

    # --- STAGE 1: VISUAL EXTRACTION ---
    prompt_vision = """
    Anda adalah asisten ekstraksi data. Perhatikan gambar sertifikat ini.
    Ekstrak data ke dalam format JSON murni:
    {
        "nama_peserta": "...",
        "jenjang_sekolah": "...",
        "nama_lomba": "...",
        "nama_penyelenggara": "..."
    }
    Jangan berikan teks tambahan atau markdown.
    """
    
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=content_type)
    
    vision_resp = await vision_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt_vision, image_part]
    )
    raw_vision_text = vision_resp.text.replace('```json', '').replace('```', '').strip()
    extracted_data = json.loads(raw_vision_text)

    # --- STAGE 2: RAG RETRIEVAL ---
    search_query = f"Aturan admisi untuk jenjang {extracted_data.get('jenjang_sekolah', '')} dan lomba {extracted_data.get('nama_lomba', '')} untuk jurusan {jurusan_tujuan}"
    retrieved_context = await query_engine.aquery(search_query)

    # --- STAGE 3: AGENTIC AUDIT ---
    prompt_auditor = f"""
    Anda adalah Auditor Admisi POLBAN Berbasis AI.
    Tugas Anda: Berikan penilaian kelayakan berdasarkan data berikut.
    
    DATA PENDAFTAR:
    {json.dumps(extracted_data, indent=2)}
    JURUSAN TUJUAN: {jurusan_tujuan}
    NAMA YANG DIHARAPKAN: {expected_name}
    
    ATURAN VALIDASI NAMA (SANGAT PENTING!):
    - Miskomunikasi nama adalah indikator fraud atau salah mengunggah file.
    - WAJIB membandingkan "nama_peserta" dari hasil ekstraksi dokumen dengan NAMA YANG DIHARAPKAN ("{expected_name}").
    - Jika namanya berbeda jauh atau jelas-jelas tidak cocok, Anda WAJIB mengubah status menjadi "Ditolak" (Berikan penjelasan di reasoning bahwa nama pada dokumen tidak sesuai dengan nama pendaftar yang diharapkan).
    
    ANTI-KECURANGAN (PENTING!):
    - Flags: {fraud_flags if fraud_flags else "Bersih (Tidak ada indikasi software editan)"}
    - QR Code / Barcode Data: {qr_data if qr_data else "Tidak ditemukan barcode"}
    (Jika Flags menunjukkan indikasi editan/Photoshop/Canva, Anda WAJIB MENGUBAH STATUS menjadi "Ditolak" karena ini sertifikat palsu, berikan skor 0).

    KONTEKS ATURAN (RAG):
    {retrieved_context.response}

    Output harus JSON murni:
    {{
        "status": "Diterima / Ditolak / Butuh Tinjauan Manual",
        "skor_kepatuhan": 0-100,
        "langkah_gagal": "Jika ada, sebutkan langkah 1-4 yang tidak terpenuhi",
        "reasoning": "Penjelasan detail mengapa status tersebut diberikan, PASTIKAN menyebutkan pencocokkan nama di sini."
    }}
    """
    
    final_resp = await llm.acomplete(prompt_auditor)
    raw_audit_text = final_resp.text.replace('```json', '').replace('```', '').strip()
    final_audit_result = json.loads(raw_audit_text)
    
    # --- STAGE 4: ASSIGN TO DATABASE ---
    new_applicant = Applicant(
        batch_id=batch_id,
        filename=filename,
        applicant_name=expected_name,
        target_major=jurusan_tujuan,
        fraud_flags=json.dumps(fraud_flags),
        qr_data=json.dumps(qr_data),
        skor_kepatuhan=final_audit_result.get("skor_kepatuhan", 0),
        ai_status=final_audit_result.get("status", "Unknown"),
        final_status=final_audit_result.get("status", "Unknown"), 
        reasoning=final_audit_result.get("reasoning", "")
    )
    db.add(new_applicant)
    await db.commit()
    await db.refresh(new_applicant)

    return {
        "metadata": {"filename": filename, "target_major": jurusan_tujuan},
        "security": {"fraud_flags": fraud_flags, "qr_data": qr_data},
        "extraction": extracted_data,
        "audit": final_audit_result,
        "id_pendaftar": new_applicant.id
    }

@app.post("/process-document")
async def process_document(
    file: UploadFile = File(...), 
    expected_name: str = Form(...),
    jurusan_tujuan: str = Form(...), 
    db: AsyncSession = Depends(get_db)
):
    try:
        import uuid
        safe_filename = f"{uuid.uuid4()}_{file.filename}"
        save_path = os.path.join("uploads", safe_filename)
        
        # Read and save file
        image_bytes = await file.read()
        with open(save_path, "wb") as f_out:
            f_out.write(image_bytes)

        return await process_single_application(
            image_bytes=image_bytes,
            filename=safe_filename,
            content_type=file.content_type,
            jurusan_tujuan=jurusan_tujuan,
            expected_name=expected_name,
            db=db
        )

    except Exception as e:
        # Menampilkan error yang lebih spesifik di console untuk debugging
        print(f"ERROR LOG: {str(e)}")
        return {"error": str(e), "detail": "Terjadi kesalahan pada pipeline AI."}

# Endpoint 2: Mengambil Semua Pendaftar (Untuk Admin Dashboard)
@app.get("/api/applicants")
async def get_applicants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant).order_by(Applicant.id.desc()))
    applicants = result.scalars().all()
    return {"data": applicants}

# Endpoint 3: Override (Human-in-the-Loop)
@app.post("/api/applicants/{applicant_id}/override")
async def override_applicant_status(applicant_id: int, status: str = Form(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant).where(Applicant.id == applicant_id))
    applicant = result.scalar_one_or_none()
    
    if not applicant:
        return {"error": "Applicant not found"}
        
    applicant.final_status = status
    await db.commit()
    await db.refresh(applicant)
    return {"message": f"Status updated to {status}", "applicant_id": applicant.id, "final_status": applicant.final_status}

# Endpoint 4: Export CSV (Phase 8)
@app.get("/api/applicants/export")
async def export_applicants_csv(db: AsyncSession = Depends(get_db)):
    from export import generate_csv_export
    csv_data = await generate_csv_export(db)
    
    return StreamingResponse(
        iter([csv_data.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=laporan_pendaftar.csv"}
    )

# Endpoint 5: Analytics Metrics (Phase 8)
@app.get("/api/applicants/metrics")
async def get_applicant_metrics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Applicant))
    applicants = result.scalars().all()
    
    total = len(applicants)
    diterima = sum(1 for a in applicants if 'diterima' in str(a.final_status).lower())
    ditolak = sum(1 for a in applicants if 'ditolak' in str(a.final_status).lower())
    fraud = sum(1 for a in applicants if a.fraud_flags and len(a.fraud_flags) > 2) # check if json list is not empty '[]'
    
    return {
        "total": total,
        "diterima": diterima,
        "ditolak": ditolak,
        "fraud": fraud
    }

# Endpoint 6: Authentication Login (Phase 9 & 10)
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
async def login_admin(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    from models import Admin
    result = await db.execute(select(Admin).where(Admin.username == request.username))
    admin_user = result.scalar_one_or_none()
    
    if admin_user and admin_user.password == request.password:
        return {"message": "Login successful", "token": "polban_admin_session_token_xyz"}
    
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Username atau Password salah")

# Endpoint 7: Batch Processing (Phase 12)
from fastapi import BackgroundTasks
import tempfile
import uuid
import shutil

async def background_batch_processor(batch_id: int, files_info: list, target_major: str):
    from database import AsyncSessionLocal
    from models import BatchJob
    
    async with AsyncSessionLocal() as db:
        for f_info in files_info:
            try:
                # Read bytes from permanent file
                with open(f_info["path"], "rb") as f:
                    image_bytes = f.read()
                
                # Run the AI logic
                await process_single_application(
                    image_bytes=image_bytes,
                    filename=f_info["saved_filename"],
                    content_type=f_info["content_type"],
                    jurusan_tujuan=target_major,
                    expected_name=f_info["expected_name"],
                    db=db,
                    batch_id=batch_id
                )
            except Exception as e:
                print(f"ERROR LOG: Batch processing failed for {f_info['filename']}: {str(e)}")
            
            # Increment processed count
            result = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
            job = result.scalar_one_or_none()
            if job:
                job.processed_files += 1
                if job.processed_files >= job.total_files:
                    job.status = "completed"
                await db.commit()

@app.post("/api/audit/batch")
async def process_batch_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...), 
    expected_names: list[str] = Form(...),
    jurusan_tujuan: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    from models import BatchJob
    
    # 1. Create a BatchJob record
    new_batch = BatchJob(total_files=len(files), processed_files=0, status="processing")
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)
    
    # 2. Save uploaded files to uploads dir synchronously for the background task to read
    files_info = []
    
    for idx, uploaded_file in enumerate(files):
        safe_filename = f"{uuid.uuid4()}_{uploaded_file.filename}"
        save_path = os.path.join("uploads", safe_filename)
        
        # Write bytes permanently
        with open(save_path, "wb") as f_out:
            file_bytes = await uploaded_file.read()
            f_out.write(file_bytes)
            
        files_info.append({
            "path": save_path,
            "filename": uploaded_file.filename,
            "saved_filename": safe_filename,
            "content_type": uploaded_file.content_type,
            "expected_name": expected_names[idx] if idx < len(expected_names) else "Unknown"
        })
        
    # 3. Dispatch to background queue
    background_tasks.add_task(background_batch_processor, new_batch.id, files_info, jurusan_tujuan)
    
    return {
        "message": "Batch processing started in the background",
        "batch_id": new_batch.id,
        "total_files": len(files)
    }

@app.get("/api/audit/batch/{batch_id}")
async def get_batch_status(batch_id: int, db: AsyncSession = Depends(get_db)):
    from models import BatchJob
    result = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    job = result.scalar_one_or_none()
    
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Batch job not found")
        
    # Also get all applicants tied to this batch (optional summary)
    app_result = await db.execute(select(Applicant).where(Applicant.batch_id == batch_id))
    batch_applicants = app_result.scalars().all()
    
    return {
        "batch_id": job.id,
        "total": job.total_files,
        "processed": job.processed_files,
        "status": job.status,
        "applicants_processed": len(batch_applicants)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)