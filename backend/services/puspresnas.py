"""
Pengecekan legalitas penyelenggara/ajang ke SIMT PUSPRESNAS (live scraping).

SIMT (Sistem Informasi Manajemen Talenta) Pusat Prestasi Nasional menyajikan
daftar ajang talenta yang telah dikurasi pada halaman server-rendered:

    GET https://simt.kemendikdasmen.go.id/kurasi/detail?organizer=<nama>&country=

Halaman mengembalikan HTML biasa (bukan SPA/JSON), sehingga dapat di-scrape.
Modul ini mengambil halaman tersebut, lalu menentukan:
  1. apakah penyelenggara terkurasi (jumlah ajang > 0), dan
  2. (opsional) apakah nama lomba pada sertifikat cocok dengan salah satu ajang.

Catatan penting:
- PUSPRESNAS TIDAK menyediakan API publik resmi; ini adalah scraping HTML dan
  dapat berubah bila tata letak situs SIMT berubah. Parsing dibuat defensif.
- Ada cache di memori + timeout + retry agar tidak membebani server SIMT.
- Fungsi publik tidak pernah melempar exception ke pipeline; kegagalan jaringan
  dikembalikan sebagai status 'checked=False' agar audit bisa menandai
  'Butuh Tinjauan Manual' untuk aspek legalitas.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("compliance.puspresnas")

SIMT_BASE_URL = "https://simt.kemendikdasmen.go.id"
SIMT_DETAIL_PATH = "/kurasi/detail"
DEFAULT_TIMEOUT = 12.0
MAX_RETRIES = 2
MATCH_THRESHOLD = 0.82
CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 jam

_USER_AGENT = (
    "Mozilla/5.0 (compatible; PolbanComplianceEngine/1.0; "
    "+https://github.com/Rddei/RAGSertifikat-PLBN)"
)

# Cache sederhana di memori proses: { kunci_normal: (waktu_simpan, hasil) }
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _normalize(text: str) -> str:
    """Normalisasi teks: tanpa diakritik, huruf kecil, hanya alfanumerik+spasi."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


_TOTAL_RE = re.compile(
    r"Menampilkan\s+[\d.,]+\s*-\s*[\d.,]+\s+dari\s+([\d.,]+)\s+data",
    re.IGNORECASE,
)


def _parse_total(text: str) -> int | None:
    """Ambil angka N dari teks 'Menampilkan 1 - 10 dari N data'."""
    m = _TOTAL_RE.search(text)
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(1))
    return int(digits) if digits else None


def _parse_listing_text(text: str) -> dict[str, Any]:
    """Parse teks halaman SIMT menjadi total + daftar ajang (best-effort).

    Sinyal utama (total) sangat stabil karena berasal dari teks paginasi.
    Daftar ajang bersifat tambahan; pencocokan lomba juga memakai substring
    pada teks penuh sehingga tetap andal walau struktur baris berubah.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]

    total = _parse_total(" ".join(lines))

    entries: list[dict[str, str]] = []
    for i, line in enumerate(lines):
        # Baris bidang berbentuk "BIDANG | Kategori | Negara" (tepat 2 pipa).
        if line.count("|") == 2 and i >= 1:
            ajang = lines[i - 1]
            bidang = line.split("|")[0].strip()
            # Hindari baris tabel kosong sebagai nama ajang.
            if ajang and ajang.count("|") == 0:
                entries.append({"ajang": ajang, "bidang": bidang})

    penyelenggara: list[str] = []
    for i, line in enumerate(lines):
        if line.lower() == "penyelenggara" and i + 1 < len(lines):
            penyelenggara.append(lines[i + 1])

    return {
        "total": total,
        "entries": entries,
        "penyelenggara": sorted(set(penyelenggara)),
        "full_text_norm": _normalize(" ".join(lines)),
    }


async def _fetch(organizer: str, timeout: float) -> str:
    """Ambil HTML halaman detail SIMT untuk satu penyelenggara (dengan retry)."""
    params = {"organizer": organizer, "country": ""}
    url = f"{SIMT_BASE_URL}{SIMT_DETAIL_PATH}?{urlencode(params)}"
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:  # noqa: BLE001 - sengaja luas, lalu retry
            last_exc = exc
            logger.warning("SIMT fetch gagal (percobaan %d): %s", attempt, exc)
            await asyncio.sleep(0.6 * attempt)
    assert last_exc is not None
    raise last_exc


def _best_match(
    nama_lomba: str, parsed: dict[str, Any]
) -> tuple[bool, float, str | None]:
    """Tentukan apakah nama_lomba cocok dengan salah satu ajang terkurasi."""
    norm_lomba = _normalize(nama_lomba)
    if not norm_lomba:
        return False, 0.0, None
    # 1) Substring langsung pada teks penuh ternormalisasi (paling andal).
    if len(norm_lomba) >= 4 and norm_lomba in parsed["full_text_norm"]:
        return True, 1.0, nama_lomba
    # 2) Fuzzy terhadap setiap nama ajang yang berhasil di-parse.
    best_score = 0.0
    best_name: str | None = None
    for entry in parsed["entries"]:
        score = SequenceMatcher(None, norm_lomba, _normalize(entry["ajang"])).ratio()
        if score > best_score:
            best_score = score
            best_name = entry["ajang"]
    return best_score >= MATCH_THRESHOLD, best_score, best_name


def _public_view(result: dict[str, Any]) -> dict[str, Any]:
    """Buang field internal (diawali '_') sebelum dikembalikan."""
    return {k: v for k, v in result.items() if not k.startswith("_")}


async def check_kurasi(
    nama_penyelenggara: str,
    nama_lomba: str | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Cek apakah penyelenggara/ajang terkurasi di SIMT PUSPRESNAS.

    Mengembalikan dict ringkas yang AMAN dipakai pipeline (tidak melempar error).
    """
    result: dict[str, Any] = {
        "checked": False,
        "terkurasi": None,
        "total_ditemukan": 0,
        "lomba_cocok": False,
        "skor_kecocokan": 0.0,
        "ajang_terdekat": None,
        "penyelenggara_query": nama_penyelenggara,
        "sumber": None,
        "error": None,
    }

    organizer = (nama_penyelenggara or "").strip()
    if not organizer:
        result["error"] = "Nama penyelenggara kosong - pengecekan dilewati."
        return result

    cache_key = _normalize(organizer)
    if use_cache and cache_key in _cache:
        ts, cached = _cache[cache_key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            merged = dict(cached)
            # Hitung ulang pencocokan lomba (murah) tanpa fetch ulang.
            if nama_lomba and cached.get("_parsed"):
                cocok, skor, terdekat = _best_match(nama_lomba, cached["_parsed"])
                merged.update(
                    lomba_cocok=cocok,
                    skor_kecocokan=round(skor, 3),
                    ajang_terdekat=terdekat,
                )
            logger.info("PUSPRESNAS cache hit untuk '%s'", organizer)
            return _public_view(merged)

    params = {"organizer": organizer, "country": ""}
    result["sumber"] = f"{SIMT_BASE_URL}{SIMT_DETAIL_PATH}?{urlencode(params)}"

    try:
        html = await _fetch(organizer, timeout)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Gagal mengakses SIMT: {exc}"
        logger.warning("Pengecekan PUSPRESNAS gagal untuk '%s': %s", organizer, exc)
        return result

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    parsed = _parse_listing_text(text)

    total = parsed["total"] or 0
    result["checked"] = True
    result["total_ditemukan"] = total
    result["terkurasi"] = total > 0

    if nama_lomba and total > 0:
        cocok, skor, terdekat = _best_match(nama_lomba, parsed)
        result["lomba_cocok"] = cocok
        result["skor_kecocokan"] = round(skor, 3)
        result["ajang_terdekat"] = terdekat

    if use_cache:
        cached_copy = dict(result)
        cached_copy["_parsed"] = parsed
        _cache[cache_key] = (time.time(), cached_copy)

    return _public_view(result)


def format_for_audit(puspresnas: dict[str, Any]) -> str:
    """Ringkasan teks untuk dimasukkan ke prompt audit / reasoning LLM."""
    if not puspresnas.get("checked"):
        return (
            "Status legalitas penyelenggara TIDAK DAPAT diverifikasi "
            f"(alasan: {puspresnas.get('error') or 'tidak diketahui'}). "
            "Perlakukan aspek legalitas sebagai 'Butuh Tinjauan Manual'."
        )
    if not puspresnas.get("terkurasi"):
        return (
            f"Penyelenggara '{puspresnas.get('penyelenggara_query')}' TIDAK DITEMUKAN "
            "dalam daftar ajang terkurasi SIMT PUSPRESNAS (0 hasil). "
            "Indikasi kuat penyelenggara tidak resmi/terkurasi."
        )
    base = (
        "Penyelenggara TERKURASI di SIMT PUSPRESNAS "
        f"({puspresnas.get('total_ditemukan')} ajang terkurasi)."
    )
    if puspresnas.get("lomba_cocok"):
        return base + (
            " Nama lomba pada sertifikat COCOK dengan ajang terkurasi "
            f"('{puspresnas.get('ajang_terdekat')}', skor "
            f"{puspresnas.get('skor_kecocokan')})."
        )
    return base + (
        " Namun nama lomba pada sertifikat TIDAK cocok persis dengan ajang "
        f"terkurasi (terdekat: '{puspresnas.get('ajang_terdekat')}', skor "
        f"{puspresnas.get('skor_kecocokan')}). Pertimbangkan tinjauan manual."
    )
