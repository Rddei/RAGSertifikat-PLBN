import os
from datetime import date, datetime

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Ambil env var wajib; error jelas bila belum di-set."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"{name} wajib di-set di .env")
    return value


# --- Wajib ---
GOOGLE_API_KEY = _require("GOOGLE_API_KEY")
SECRET_KEY = _require("SECRET_KEY")            # kunci untuk menandatangani JWT
ADMIN_PASSWORD = _require("ADMIN_PASSWORD")    # password admin awal (akan di-hash)

# --- Opsional (punya default) ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")  # HARUS sama antara indexer & query
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./compliance.db")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # set "production" saat deploy

# Daftar origin frontend yang boleh mengakses API (dipisah koma)
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]

IS_PRODUCTION = ENVIRONMENT.lower() == "production"

# ---------------------------------------------------------------------------
# Tanggal acuan sistem ("hari ini")
# ---------------------------------------------------------------------------
# Model AI cenderung "berhalusinasi" menganggap ajang di tahun berjalan BELUM
# terjadi karena tidak punya acuan waktu (asumsi masih di sekitar batas latih
# modelnya). Untuk itu tanggal hari ini disuntikkan ke prompt audit.
#
# Default: tanggal sistem sekarang (date.today()) -> selalu benar mengikuti jam
# server. Untuk pengujian/simulasi, override lewat env APP_CURRENT_DATE dengan
# format YYYY-MM-DD, contoh:
#     APP_CURRENT_DATE=2026-07-20
_APP_CURRENT_DATE_RAW = os.getenv("APP_CURRENT_DATE", "").strip()

_BULAN_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def get_today() -> date:
    """Tanggal acuan sistem. Override via env APP_CURRENT_DATE bila di-set."""
    if _APP_CURRENT_DATE_RAW:
        try:
            return datetime.strptime(_APP_CURRENT_DATE_RAW, "%Y-%m-%d").date()
        except ValueError:
            # Format salah -> abaikan, pakai tanggal sistem.
            pass
    return date.today()


def today_str_id() -> str:
    """Tanggal hari ini dalam format Indonesia, mis. '20 Juli 2026'."""
    d = get_today()
    return f"{d.day} {_BULAN_ID[d.month - 1]} {d.year}"


# ---------------------------------------------------------------------------
# Data SIMT hasil scraping (kurasi lokal / offline)
# ---------------------------------------------------------------------------
# Berkas keluaran tools/scrape_simt.py. Diutamakan .jsonl (ringan, tanpa Excel),
# dengan fallback otomatis ke .xlsx bila hanya itu yang tersedia.
SIMT_DATA_PATH = os.getenv("SIMT_DATA_PATH", "./data_simt/simt_ajang.jsonl")
# Ambang kemiripan (0..1) untuk mencocokkan nama ajang & penyelenggara.
KURASI_ORG_THRESHOLD = float(os.getenv("KURASI_ORG_THRESHOLD", "0.80"))
KURASI_NAME_THRESHOLD = float(os.getenv("KURASI_NAME_THRESHOLD", "0.72"))
