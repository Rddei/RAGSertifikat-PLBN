FROM python:3.11-slim

# Hindari file .pyc, aktifkan log realtime, dan set Zona Waktu
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Jakarta

# Paket sistem:
#   libzbar0 -> wajib untuk pyzbar (pemindaian QR/barcode)
#   curl     -> dipakai HEALTHCHECK
#   tzdata   -> memastikan zona waktu OS berjalan dengan benar
RUN apt-get update \
    && apt-get install -y --no-install-recommends libzbar0 curl tzdata \
    && rm -rf /var/lib/apt/lists/*

# PRAKTIK KEAMANAN TERBAIK:
# Buat user non-root SEBELUM menyalin file
RUN useradd -m appuser

WORKDIR /app

# Salin requirements dengan kepemilikan appuser
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Salin seluruh kode aplikasi dengan kepemilikan appuser
# (Mencegah error Permission Denied saat Admin mengedit Knowledge Base)
COPY --chown=appuser:appuser . .

# Buat folder data persisten + salin data kriteria ke /app/kriteria.
# PENTING: /app/kriteria berada DI LUAR mount volume 'app_data' (/app/data),
# sehingga file kriteria selalu ikut versi terbaru setiap build image --
# tidak tertutup volume lama (akar FileNotFoundError sebelumnya).
RUN mkdir -p /app/data/chroma_db /app/data/uploads /app/knowledge_base/data /app/kriteria && cp data/kriteria_prodi.json /app/kriteria/kriteria_prodi.json && chown -R appuser:appuser /app/data /app/knowledge_base /app/kriteria

# Ganti ke user non-root untuk menjalankan aplikasi
USER appuser

EXPOSE 8000

# Health check memanfaatkan endpoint /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]
