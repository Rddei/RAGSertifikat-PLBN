"""
Pengecekan KEASLIAN SERTIFIKAT via "Cek Portofolio Prestasi" SIMT PUSPRESNAS.

Berbeda dengan services/puspresnas.py (yang mengecek legalitas PENYELENGGARA),
modul ini memverifikasi apakah PRESTASI/siswa atas nama tertentu benar-benar
terdaftar pada pangkalan data talenta SIMT, berdasarkan NISN (utama) atau nama.

ENDPOINT (dikonfirmasi dari Network tab situs SIMT):
    GET https://simt.kemendikdasmen.go.id/api/search-sekolah-and-siswa?search=<kata kunci>
    - Header wajib   : Accept: application/json, Referer: https://simt.kemendikdasmen.go.id/
    - Cookie wajib   : already_filled=true  (tanpa ini server dapat menolak/redirect)
    - Parameter      : 'search' tunggal, boleh berisi NISN ATAU nama peserta didik
    - Respons        : JSON (berisi hasil pencarian sekolah DAN siswa)

KONTRAK PENTING (sama seperti modul penyelenggara):
- Fungsi publik TIDAK PERNAH melempar exception ke pipeline. Kegagalan jaringan
  dikembalikan sebagai 'checked=False' agar audit menandai aspek keaslian
  sertifikat sebagai 'Butuh Tinjauan Manual'.
- Ada cache di memori + timeout + retry agar tidak membebani server SIMT.

Konfigurasi dapat ditimpa via variabel lingkungan (umumnya tidak perlu):
    SIMT_PORTOFOLIO_PATH         (default: "/api/search-sekolah-and-siswa")
    SIMT_PORTOFOLIO_PARAM_SEARCH (default: "search")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("compliance.portfolio")

SIMT_BASE_URL = "https://simt.kemendikdasmen.go.id"
SIMT_PORTOFOLIO_PATH = os.getenv("SIMT_PORTOFOLIO_PATH", "/api/search-sekolah-and-siswa")
PARAM_SEARCH = os.getenv("SIMT_PORTOFOLIO_PARAM_SEARCH", "search")

DEFAULT_TIMEOUT = 12.0
MAX_RETRIES = 2
NAME_MATCH_THRESHOLD = 0.82
CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 jam

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Cache di memori proses: { kunci_normal: (waktu_simpan, hasil_lengkap) }
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


# --------------------------------------------------------------------------- #
# Util normalisasi                                                            #
# --------------------------------------------------------------------------- #
def _normalize(text: str) -> str:
    """Normalisasi: tanpa diakritik, huruf kecil, hanya alfanumerik + spasi."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _clean_nisn(nisn: str) -> str:
    """Sisakan digit saja dari NISN/NPSN."""
    return re.sub(r"[^0-9]", "", nisn or "")


# --------------------------------------------------------------------------- #
# Ekstraksi rekaman siswa dari JSON (defensif terhadap perubahan skema)        #
# --------------------------------------------------------------------------- #
def _iter_dicts(obj: Any):
    """Telusuri seluruh dict dalam struktur JSON secara rekursif."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


def _find_keyed_lists(obj: Any, pattern: str) -> list[list]:
    """Cari list yang berada di bawah key yang namanya cocok 'pattern'."""
    found: list[list] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and re.search(pattern, str(k), re.I):
                found.append(v)
            found.extend(_find_keyed_lists(v, pattern))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_find_keyed_lists(v, pattern))
    return found


def _field(d: dict, pattern: str) -> str:
    """Ambil nilai skalar pertama yang key-nya cocok 'pattern'."""
    for k, v in d.items():
        if re.search(pattern, str(k), re.I) and isinstance(v, (str, int, float)):
            s = str(v).strip()
            if s:
                return s
    return ""


def _student_name(d: dict) -> str:
    # Utamakan key spesifik siswa, lalu fallback ke 'nama' umum.
    for pat in (r"nama_siswa", r"nama_peserta", r"^nama$", r"student.*name", r"^name$"):
        val = _field(d, pat)
        if val:
            return val
    return _field(d, r"nama")


def _student_school(d: dict) -> str:
    return _field(d, r"sekolah|satuan_pendidikan|asal")


def _looks_like_student(d: dict) -> bool:
    """Heuristik: rekaman siswa bila punya NISN, atau punya nama+sekolah."""
    if _field(d, r"nisn"):
        return True
    return bool(_student_name(d) and _student_school(d))


def _unwrap(data: Any) -> Any:
    """Turun ke payload inti bila dibungkus envelope {status, message, result}."""
    if isinstance(data, dict):
        for key in ("result", "results", "data"):
            inner = data.get(key)
            if isinstance(inner, (dict, list)):
                return inner
    return data


def _extract_students(data: Any) -> list[dict]:
    """Kumpulkan rekaman siswa dari respons JSON, sefleksibel mungkin."""
    root = _unwrap(data)
    # 1) Prioritas: list di bawah key bernuansa siswa/peserta/didik.
    students: list[dict] = []
    for lst in _find_keyed_lists(root, r"siswa|peserta|didik|student"):
        students.extend(x for x in lst if isinstance(x, dict))
    if students:
        return students
    # 2) Fallback: seluruh dict yang "tampak" seperti rekaman siswa.
    return [d for d in _iter_dicts(root) if _looks_like_student(d)]


def _match_name(nama_peserta: str, students: list[dict]) -> tuple[bool, float]:
    """Skor kecocokan nama peserta terhadap daftar siswa hasil pencarian."""
    target = _normalize(nama_peserta)
    if not target:
        return False, 0.0
    best = 0.0
    for s in students:
        cand = _normalize(_student_name(s))
        if not cand:
            continue
        if target == cand or (len(target) >= 4 and target in cand):
            return True, 1.0
        best = max(best, SequenceMatcher(None, target, cand).ratio())
    return best >= NAME_MATCH_THRESHOLD, best


# --------------------------------------------------------------------------- #
# HTTP                                                                         #
# --------------------------------------------------------------------------- #
class EndpointMisconfigured(Exception):
    """Endpoint/parameter portofolio salah (HTTP 4xx). Tidak perlu retry."""


def _build_url(search: str) -> str:
    return f"{SIMT_BASE_URL}{SIMT_PORTOFOLIO_PATH}?{urlencode({PARAM_SEARCH: search})}"


async def _fetch_json(url: str, timeout: float) -> Any:
    """Ambil JSON dari endpoint pencarian SIMT (retry hanya untuk error transien)."""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{SIMT_BASE_URL}/",
        "User-Agent": _USER_AGENT,
    }
    cookies = {"already_filled": "true"}
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, cookies=cookies
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                try:
                    return resp.json()
                except (json.JSONDecodeError, ValueError):
                    return json.loads(resp.text)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if 400 <= status < 500:
                raise EndpointMisconfigured(
                    f"HTTP {status} pada {url} - path/parameter portofolio SIMT "
                    f"kemungkinan belum benar (lihat SIMT_PORTOFOLIO_PATH / "
                    f"SIMT_PORTOFOLIO_PARAM_SEARCH)."
                ) from exc
            last_exc = exc  # 5xx: layak diulang
            logger.warning("SIMT portofolio fetch gagal (percobaan %d): %s", attempt, exc)
            await asyncio.sleep(0.6 * attempt)
        except Exception as exc:  # noqa: BLE001 - gangguan jaringan/parse: retry
            last_exc = exc
            logger.warning("SIMT portofolio fetch gagal (percobaan %d): %s", attempt, exc)
            await asyncio.sleep(0.6 * attempt)
    assert last_exc is not None
    raise last_exc


def _public_view(result: dict[str, Any]) -> dict[str, Any]:
    """Buang field internal (diawali '_') sebelum dikembalikan."""
    return {k: v for k, v in result.items() if not k.startswith("_")}


# --------------------------------------------------------------------------- #
# API publik                                                                   #
# --------------------------------------------------------------------------- #
async def check_portfolio(
    nisn: str = "",
    nama_peserta: str = "",
    nama_lomba: str | None = None,
    asal_sekolah: str | None = None,
    npsn: str = "",
    *,
    timeout: float = DEFAULT_TIMEOUT,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Cek keaslian sertifikat lewat pencarian portofolio SIMT PUSPRESNAS.

    Strategi kunci: NISN diutamakan (paling unik); bila kosong, gunakan nama.
    SELALU mengembalikan dict aman (tidak pernah melempar error ke pipeline).
    """
    nisn_clean = _clean_nisn(nisn)
    nama_clean = (nama_peserta or "").strip()

    result: dict[str, Any] = {
        "checked": False,
        "terdaftar": None,
        "total_ditemukan": 0,
        "nisn_cocok": False,
        "nama_cocok": False,
        "skor_kecocokan_nama": 0.0,
        "kunci_pencarian": None,
        "nisn_query": nisn_clean,
        "nama_query": nama_clean,
        "kandidat": [],
        # 'tinggi' (NISN cocok) | 'sedang' (nama unik) | 'rendah' (nama ambigu) |
        # 'tidak_ditemukan' | 'tidak_terverifikasi'
        "tingkat_keyakinan": "tidak_terverifikasi",
        "ambigu": False,
        "sumber": None,
        "error": None,
    }

    if not nisn_clean and not nama_clean:
        result["error"] = "NISN dan nama peserta kosong - pengecekan portofolio dilewati."
        return result

    # Kunci pencarian: utamakan NISN.
    if nisn_clean:
        search_term = nisn_clean
        result["kunci_pencarian"] = "nisn"
        cache_key = f"nisn:{nisn_clean}"
    else:
        search_term = nama_clean
        result["kunci_pencarian"] = "nama"
        cache_key = f"nama:{_normalize(nama_clean)}"

    if use_cache and cache_key in _cache:
        ts, cached = _cache[cache_key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            logger.info("Portofolio cache hit untuk '%s'", cache_key)
            return _public_view(cached)

    url = _build_url(search_term)
    result["sumber"] = url

    try:
        data = await _fetch_json(url, timeout)
    except EndpointMisconfigured as exc:
        result["error"] = (
            f"Endpoint portofolio SIMT belum dikonfigurasi dengan benar: {exc} "
            "Periksa kembali SIMT_PORTOFOLIO_PATH / SIMT_PORTOFOLIO_PARAM_SEARCH."
        )
        logger.error("Endpoint portofolio SIMT salah untuk '%s': %s", cache_key, exc)
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Gagal mengakses SIMT portofolio: {exc}"
        logger.warning("Pengecekan portofolio gagal untuk '%s': %s", cache_key, exc)
        return result

    students = _extract_students(data)
    if not students:
        # Bisa berarti 0 hasil sah, atau skema berbeda. Simpan cuplikan untuk diagnosa.
        inner = data.get("result") if isinstance(data, dict) else data
        logger.info(
            "Portofolio: 0 rekaman siswa terbaca untuk '%s'. Cuplikan result=%s",
            cache_key, str(inner)[:300],
        )

    result["checked"] = True
    result["total_ditemukan"] = len(students)
    result["terdaftar"] = len(students) > 0
    result["kandidat"] = [
        {
            "nama": _student_name(s),
            "nisn": _clean_nisn(_field(s, r"nisn")),
            "sekolah": _student_school(s),
        }
        for s in students[:5]
    ]

    # Konfirmasi tambahan.
    if nisn_clean:
        result["nisn_cocok"] = any(
            _clean_nisn(_field(s, r"nisn")) == nisn_clean for s in students
        )
    if nama_clean:
        cocok, skor = _match_name(nama_clean, students)
        result["nama_cocok"] = cocok
        result["skor_kecocokan_nama"] = round(skor, 3)

    # Tingkat keyakinan identitas. NISN = kunci unik; nama saja rawan homonim.
    if not result["terdaftar"]:
        result["tingkat_keyakinan"] = "tidak_ditemukan"
    elif result["kunci_pencarian"] == "nisn" and result["nisn_cocok"]:
        result["tingkat_keyakinan"] = "tinggi"
    elif result["kunci_pencarian"] == "nama":
        if result["total_ditemukan"] > 1:
            # Lebih dari satu orang bernama sama -> tidak bisa dipastikan.
            result["ambigu"] = True
            result["tingkat_keyakinan"] = "rendah"
        elif result["nama_cocok"]:
            result["tingkat_keyakinan"] = "sedang"
        else:
            result["tingkat_keyakinan"] = "rendah"
    else:
        result["tingkat_keyakinan"] = "sedang"

    if use_cache:
        _cache[cache_key] = (time.time(), dict(result))

    return _public_view(result)


def format_for_audit_portfolio(portfolio: dict[str, Any]) -> str:
    """Ringkasan teks untuk dimasukkan ke prompt audit / reasoning LLM."""
    if not portfolio.get("checked"):
        return (
            "Keaslian sertifikat TIDAK DAPAT diverifikasi via portofolio SIMT "
            f"(alasan: {portfolio.get('error') or 'tidak diketahui'}). "
            "Perlakukan aspek keaslian sertifikat sebagai 'Butuh Tinjauan Manual'."
        )

    kunci = portfolio.get("kunci_pencarian")
    ref = (
        f"NISN {portfolio.get('nisn_query')}"
        if kunci == "nisn"
        else f"nama '{portfolio.get('nama_query')}'"
    )

    if not portfolio.get("terdaftar"):
        return (
            f"Data peserta atas {ref} TIDAK DITEMUKAN pada pangkalan data talenta "
            "SIMT PUSPRESNAS (0 hasil). Indikasi kuat sertifikat/prestasi tidak "
            "terdaftar atau tidak resmi."
        )

    base = (
        f"Data peserta DITEMUKAN pada SIMT PUSPRESNAS "
        f"({portfolio.get('total_ditemukan')} hasil, dicari via {kunci})."
    )
    if kunci == "nisn":
        if portfolio.get("nisn_cocok"):
            base += " NISN cocok persis dengan data SIMT."
        if portfolio.get("nama_query"):
            base += (
                " Nama peserta COCOK dengan data SIMT."
                if portfolio.get("nama_cocok")
                else " Namun nama peserta TIDAK terkonfirmasi (pertimbangkan tinjauan manual)."
            )
    else:  # pencarian via nama
        if portfolio.get("ambigu"):
            base += (
                f" PERHATIAN: ditemukan {portfolio.get('total_ditemukan')} orang dengan nama "
                "serupa di SIMT - TIDAK dapat dipastikan orang yang sama tanpa NISN. "
                "Perlakukan sebagai indikatif dan sarankan verifikasi manual."
            )
        else:
            base += (
                f" Nama peserta {'COCOK' if portfolio.get('nama_cocok') else 'TIDAK persis cocok'} "
                f"(skor {portfolio.get('skor_kecocokan_nama')}). Catatan: pencarian via nama "
                "TIDAK menjamin identitas unik karena NISN tidak tersedia pada sertifikat."
            )
    return base
