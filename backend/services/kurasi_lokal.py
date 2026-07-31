"""
Pengecekan kurasi ajang/penyelenggara secara LOKAL (offline) memakai data hasil
scraping SIMT PUSPRESNAS (tools/scrape_simt.py -> simt_ajang.jsonl / .xlsx).

Berbeda dengan services/puspresnas.py yang men-scrape LIVE per-request, modul ini
memuat SELURUH daftar ajang terkurasi (±6.000 baris) satu kali ke memori, lalu
mencocokkan sertifikat terhadap daftar tersebut -- MENIRU cara verifikasi manual:
cocokkan NAMA AJANG (+ singkatan) DAN PENYELENGGARA sekaligus. Dengan begitu tahan
terhadap 'jebakan' nama mirip (mis. banyak 'Olimpiade Sains Nasional' tiruan
swasta yang BUKAN OSN resmi -> nama mirip, penyelenggara beda).

Klasifikasi per sertifikat:
  - "Terkurasi"        : penyelenggara & nama ajang sama-sama cocok di daftar.
  - "Perlu Verifikasi" : hanya salah satu yang cocok (indikasi nama mirip / beda
                         edisi-tahun) -> serahkan ke verifikator manusia.
  - "Tidak Terkurasi"  : tidak ada padanan yang meyakinkan.

Fungsi publik TIDAK pernah melempar exception ke pipeline; bila data gagal dimuat,
dikembalikan checked=False agar audit menandai 'Butuh Tinjauan Manual'.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from config import (
    SIMT_DATA_PATH,
    KURASI_ORG_THRESHOLD,
    KURASI_NAME_THRESHOLD,
)

logger = logging.getLogger("compliance.kurasi_lokal")

# Kata umum yang TIDAK membedakan identitas ajang (dibuang dari token bermakna
# saat prefilter/kunci token). Membantu menghindari false-positive nama mirip.
_STOPWORDS = {
    "kejuaraan", "kejurnas", "kejurda", "kejurkab", "kejurcab", "kejurwil",
    "piala", "cup", "open", "championship", "tournament", "turnamen",
    "tingkat", "nasional", "internasional", "provinsi", "kabupaten", "kota",
    "antar", "pelajar", "tahun", "seri", "series", "the", "dan", "of", "and",
    "ke", "se", "competition", "kompetisi", "lomba", "festival", "olimpiade",
    "juara", "putra", "putri", "umum", "junior", "senior", "remaja",
    # Label peran kepanitiaan -- bukan identitas instansi penyelenggara.
    "panitia", "kepanitiaan", "pelaksana", "penyelenggara",
}


def _norm(text: Any) -> str:
    """Normalisasi: tanpa diakritik, huruf kecil, hanya alfanumerik + spasi."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if len(t) >= 3}


def _content_tokens(text: str) -> set[str]:
    """Token 'bermakna' (buang kata umum: kejuaraan/piala/tingkat, dsb.)."""
    return {t for t in _tokens(text) if t not in _STOPWORDS}


def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Pemuatan data (lazy singleton, reload otomatis bila file berubah)
# ---------------------------------------------------------------------------
_INDEX: dict[str, Any] = {"path": None, "mtime": None, "rows": []}


def _resolve_data_path() -> Path | None:
    """Temukan berkas data SIMT; utamakan SIMT_DATA_PATH, lalu fallback umum."""
    candidates: list[Path] = []
    p = Path(SIMT_DATA_PATH)
    candidates.append(p)
    if p.suffix == ".jsonl":
        candidates.append(p.with_suffix(".xlsx"))
    elif p.suffix == ".xlsx":
        candidates.append(p.with_suffix(".jsonl"))
    for base in ("data_simt", "tools/data_simt", "."):
        candidates.append(Path(base) / "simt_ajang.jsonl")
        candidates.append(Path(base) / "simt_ajang.xlsx")
    seen: set[str] = set()
    for c in candidates:
        key = str(c)
        if key in seen:
            continue
        seen.add(key)
        if c.exists():
            return c
    return None


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _load_xlsx(path: Path) -> list[dict]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h is not None else "" for h in next(it)]
    # Peta label kolom Excel -> key internal (samakan dengan JSONL scraper).
    label_to_key = {
        "Nama Ajang": "nama_ajang", "Singkatan": "singkatan",
        "Penyelenggara": "penyelenggara", "Level": "level",
        "Kategori": "kategori", "Cabang": "cabang", "Negara": "negara",
        "Tipe": "tipe", "Link": "link",
    }
    rows: list[dict] = []
    for values in it:
        rec: dict[str, Any] = {}
        for h, v in zip(headers, values):
            key = label_to_key.get(h, _norm(h).replace(" ", "_"))
            rec[key] = v
        if rec.get("nama_ajang") or rec.get("penyelenggara"):
            rows.append(rec)
    wb.close()
    return rows


def _get_index() -> list[dict]:
    """Kembalikan daftar ajang ter-precompute; muat/refresh bila perlu."""
    path = _resolve_data_path()
    if path is None:
        return _INDEX["rows"]  # mungkin kosong; caller menangani.
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _INDEX["rows"]
    if _INDEX["path"] == str(path) and _INDEX["mtime"] == mtime:
        return _INDEX["rows"]

    raw = _load_jsonl(path) if path.suffix == ".jsonl" else _load_xlsx(path)
    rows: list[dict] = []
    for r in raw:
        na = str(r.get("nama_ajang") or "")
        sg = str(r.get("singkatan") or "")
        pen = str(r.get("penyelenggara") or "")
        rows.append({
            "nama_ajang": na,
            "singkatan": sg,
            "penyelenggara": pen,
            "level": str(r.get("level") or ""),
            "kategori": str(r.get("kategori") or ""),
            "n_nama": _norm(na),
            "n_singkatan": _norm(sg),
            "n_peny": _norm(pen),
            "tok": _content_tokens(na) | _content_tokens(sg),
            "tok_peny": _content_tokens(pen),
        })
    _INDEX.update(path=str(path), mtime=mtime, rows=rows)
    logger.info("Kurasi lokal: memuat %d ajang terkurasi dari %s", len(rows), path)
    return rows


def _result(**over: Any) -> dict:
    base = {
        "checked": False,
        "status": "Tidak Diketahui",
        "terkurasi": None,
        "skor_nama": 0.0,
        "skor_penyelenggara": 0.0,
        "ajang_terdekat": None,
        "penyelenggara_terdekat": None,
        "level_terdekat": None,
        "kategori_terdekat": None,
        "jumlah_data": 0,
        "sumber": "SIMT lokal (hasil scraping)",
        "error": None,
    }
    base.update(over)
    return base


def check_kurasi_lokal(
    nama_lomba: str,
    singkatan: str = "",
    nama_penyelenggara: str = "",
    tingkat: str = "",
) -> dict:
    """Cocokkan satu sertifikat ke daftar ajang terkurasi SIMT (lokal).

    AMAN dipakai pipeline (tidak melempar error). Meniru verifikasi manual:
    kombinasikan kemiripan NAMA AJANG dan PENYELENGGARA.
    """
    rows = _get_index()
    if not rows:
        return _result(
            error=("Data SIMT lokal tidak tersedia. Jalankan tools/scrape_simt.py "
                   "lalu set SIMT_DATA_PATH ke berkas hasilnya."),
        )

    n_lomba = _norm(nama_lomba)
    n_sing = _norm(singkatan)
    n_peny = _norm(nama_penyelenggara)
    # Pecah string penyelenggara menjadi kandidat instansi: pemisah koma,
    # titik-koma, garis miring, atau kata 'dan'. String utuh tetap ikut
    # sebagai kandidat (menjaga kompatibilitas boost-substring lama).
    peny_candidates = [
        _norm(c) for c in re.split(r"[;,/]| dan ", str(nama_penyelenggara or ""))
        if _norm(c)
    ]
    if n_peny and n_peny not in peny_candidates:
        peny_candidates.append(n_peny)
    q_tok = _content_tokens(nama_lomba) | _content_tokens(singkatan)
    q_ptok = _content_tokens(nama_penyelenggara)

    if not (n_lomba or n_sing):
        return _result(
            checked=True, status="Perlu Verifikasi", terkurasi=False,
            jumlah_data=len(rows),
            error="Nama lomba kosong pada hasil ekstraksi.",
        )

    best: tuple[float, float, float, dict] | None = None
    for row in rows:
        # Prefilter cepat: butuh irisan token nama ATAU penyelenggara.
        if q_tok and not (q_tok & row["tok"]) and not (q_ptok & row["tok_peny"]):
            continue

        # --- Skor kemiripan nama ajang ---
        name_sim = _sim(n_lomba, row["n_nama"])
        if n_sing and row["n_singkatan"] and n_sing == row["n_singkatan"]:
            name_sim = max(name_sim, 0.95)  # singkatan sama persis = sinyal kuat
        if len(n_lomba) >= 6 and (n_lomba in row["n_nama"] or row["n_nama"] in n_lomba):
            name_sim = max(name_sim, 0.90)

        # --- Skor kemiripan penyelenggara (multi-kandidat) ---
        # Sertifikat lazim mencantumkan beberapa instansi sekaligus (mis.
        # Pemkab + KONI + federasi cabang). Semantik yang benar: MINIMAL SATU
        # instansi yang tercantum adalah penyelenggara terdaftar di SIMT.
        # Tiap kandidat diskor terpisah lalu diambil maksimum, sehingga
        # instansi pengesah/pembina tidak "mencemari" skor penyelenggara asli.
        org_sim, org_match = 0.0, ""
        for cand in (peny_candidates or [n_peny]):
            if not cand:
                continue
            s = _sim(cand, row["n_peny"])
            if len(cand) >= 5 and (cand in row["n_peny"] or row["n_peny"] in cand):
                s = max(s, 0.90)
            if s > org_sim:
                org_sim, org_match = s, cand

        combined = 0.6 * name_sim + 0.4 * org_sim
        if best is None or combined > best[0]:
            best = (combined, name_sim, org_sim, row)

    if best is None:
        return _result(checked=True, status="Tidak Terkurasi",
                       terkurasi=False, jumlah_data=len(rows))

    _, name_sim, org_sim, row = best
    name_ok = name_sim >= KURASI_NAME_THRESHOLD
    org_ok = org_sim >= KURASI_ORG_THRESHOLD

    if name_ok and org_ok:
        status, terkurasi = "Terkurasi", True
    elif name_ok or org_ok:
        status, terkurasi = "Perlu Verifikasi", False
    else:
        status, terkurasi = "Tidak Terkurasi", False

    return _result(
        checked=True,
        status=status,
        terkurasi=terkurasi,
        skor_nama=round(name_sim, 3),
        skor_penyelenggara=round(org_sim, 3),
        ajang_terdekat=row["nama_ajang"],
        penyelenggara_terdekat=row["penyelenggara"],
        level_terdekat=row["level"],
        kategori_terdekat=row["kategori"],
        jumlah_data=len(rows),
    )


def format_for_audit_kurasi(k: dict | None) -> str:
    """Ringkasan teks untuk disuntikkan ke prompt audit / reasoning LLM."""
    if not k:
        return "Pengecekan kurasi SIMT (lokal) tidak dijalankan."
    if not k.get("checked"):
        return (
            "Status kurasi SIMT TIDAK DAPAT diverifikasi "
            f"(alasan: {k.get('error') or 'tidak diketahui'}). "
            "Perlakukan aspek kurasi sebagai 'Butuh Tinjauan Manual'."
        )
    terdekat = k.get("ajang_terdekat")
    peny = k.get("penyelenggara_terdekat")
    sn = k.get("skor_nama")
    so = k.get("skor_penyelenggara")
    status = k.get("status")
    if status == "Terkurasi":
        return (
            "TERKURASI di daftar SIMT: cocok dengan ajang "
            f"'{terdekat}' (penyelenggara '{peny}', level {k.get('level_terdekat')}; "
            f"skor nama {sn}, skor penyelenggara {so})."
        )
    if status == "Perlu Verifikasi":
        return (
            "PERLU VERIFIKASI: hanya sebagian cocok dengan ajang "
            f"'{terdekat}' (penyelenggara '{peny}'; skor nama {sn}, "
            f"skor penyelenggara {so}). Waspadai nama mirip / beda edisi-tahun; "
            "serahkan ke verifikator manusia."
        )
    return (
        "TIDAK DITEMUKAN padanan meyakinkan di daftar ajang terkurasi SIMT "
        f"(kandidat terdekat: '{terdekat}', skor nama {sn}). "
        "Indikasi ajang/penyelenggara tidak terkurasi."
    )
