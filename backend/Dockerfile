FROM python:3.11-slim

# Hindari file .pyc & aktifkan log realtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Paket sistem:
#   libzbar0 -> wajib untuk pyzbar (pemindaian QR/barcode)
#   curl     -> dipakai HEALTHCHECK
# Catatan: bila build dependency (mis. chromadb) gagal, tambahkan build-essential.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libzbar0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependency lebih dulu agar layer cache efektif
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Salin seluruh kode aplikasi
COPY . .

# Folder data persisten (DB, ChromaDB, upload)
RUN mkdir -p /app/data/chroma_db /app/data/uploads

# Jalankan sebagai user non-root (praktik keamanan)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check memanfaatkan endpoint /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
