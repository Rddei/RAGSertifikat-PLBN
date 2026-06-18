# Panduan Deployment

POLBAN Intelligent Compliance Engine (backend FastAPI).

---

## 1. Persiapan `.env`

Salin contoh lalu isi nilainya:

```bash
cp .env.example .env
```

Isi minimal yang **wajib**:

| Variabel | Keterangan |
|---|---|
| `GOOGLE_API_KEY` | API key Google Gemini |
| `SECRET_KEY` | Kunci penandatangan JWT. Buat dengan: `openssl rand -hex 32` |
| `ADMIN_PASSWORD` | Password admin awal (akan otomatis di-hash) |

Untuk produksi, set juga:

```env
ENVIRONMENT=production
CORS_ORIGINS=https://domain-frontend-anda.com
```

> `ENVIRONMENT=production` otomatis menyembunyikan `/docs` & `/redoc`.

---

## 2. Jalankan dengan Docker Compose (disarankan)

```bash
docker compose up -d --build
```

- API tersedia di `http://localhost:8000`
- Cek kesehatan: `curl http://localhost:8000/health`
- Lihat log: `docker compose logs -f backend`
- Hentikan: `docker compose down` (data tetap aman di volume `app_data`)

Semua data (SQLite, ChromaDB, upload) tersimpan di volume `app_data`, jadi tidak hilang saat container di-restart.

---

## 3. Jalankan dengan Docker saja

```bash
docker build -t polban-compliance .
docker run -d -p 8000:8000 --env-file .env \
  -v polban_data:/app/data \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/compliance.db \
  -e CHROMA_DB_PATH=/app/data/chroma_db \
  -e UPLOAD_DIR=/app/data/uploads \
  --name polban-api polban-compliance
```

---

## 4. Jalankan tanpa Docker (lokal/dev)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Linux: sudo apt-get install libzbar0   (wajib untuk pyzbar)
# macOS: brew install zbar
uvicorn main:app --reload
```

---

## 5. Catatan produksi

- **Reverse proxy**: letakkan di belakang Nginx/Caddy untuk TLS (HTTPS) dan rate limiting.
- **Knowledge base**: pastikan PDF pedoman sudah di-index ke ChromaDB sebelum melayani permintaan (lihat `knowledge_base/indexer.py`).
- **Skalabilitas**: SQLite cocok untuk skala kecil. Untuk beban tinggi, pertimbangkan PostgreSQL (ganti `DATABASE_URL` ke `postgresql+asyncpg://...`).
- **Backup**: backup berkala volume `app_data` (berisi DB + ChromaDB).
- **Workers**: untuk trafik lebih besar jalankan via Gunicorn:
  `gunicorn -k uvicorn.workers.UvicornWorker -w 4 main:app`
- **Secret**: jangan pernah commit file `.env`. Gunakan secret manager bila tersedia.
