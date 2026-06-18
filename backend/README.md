# POLBAN Intelligent Compliance Engine — Backend

Mesin verifikasi sertifikat untuk admisi POLBAN.
Pipeline: **Fraud Detection -> Vision Extraction -> RAG Retrieval -> Agentic Audit -> Persist**.

## Struktur folder

```
backend/
  main.py                     # Entry point FastAPI (REKONSTRUKSI - mohon dicek)
  config.py                   # Konfigurasi dari .env
  export.py                   # Ekspor data pendaftar ke CSV
  debug.py                    # Smoke test import aplikasi
  requirements.txt
  .env.example

  models/
    database.py               # SQLAlchemy async: Admin, BatchJob, Applicant
    schemas.py                # Skema Pydantic (request/response)

  services/
    fraud.py                  # Deteksi editan (EXIF) + baca QR
    compliance_service.py     # Pembungkus pipeline

  core/
    vision.py                 # Ekstraksi data sertifikat (Gemini Vision)
    retrieval.py              # Ambil aturan dari knowledge base (RAG)
    audit.py                  # Penilaian akhir (Gemini LLM)
    agent.py                  # Orkestrasi seluruh pipeline

  repositories/
    chromadb_repo.py          # Koneksi ChromaDB + query engine

  api/routes/
    auth.py                   # Login admin
    documents.py              # POST /process-document (single)
    batch.py                  # Batch processing
    applicants.py             # List, export, metrics, override

  knowledge_base/
    indexer.py                # Bangun index dari PDF di knowledge_base/data/
    data/                     # Taruh PDF pedoman di sini

  uploads/                    # File hasil upload (batch)
```

## Menjalankan (lokal)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # lalu isi GOOGLE_API_KEY

# 1) Bangun knowledge base (sekali, setelah menaruh PDF di knowledge_base/data/)
python knowledge_base/indexer.py

# 2) Jalankan server
uvicorn main:app --reload
```

Buka dokumentasi interaktif di http://localhost:8000/docs

## Catatan

Ini adalah **baseline (kode asli)** yang disusun ulang ke struktur folder.
Perbaikan keamanan & reliabilitas (hash password, JWT, CORS, dll.) belum
diterapkan di sini dan akan dilakukan pada tahap berikutnya.
