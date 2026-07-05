#!/usr/bin/env python3
"""
cek_portofolio.py - Pengecek keaslian sertifikat via "Cek Portofolio Prestasi" SIMT.

File MANDIRI (standalone): tidak butuh struktur project (services/core).
Berguna untuk menguji & menyetel endpoint terhadap situs SIMT yang nyata, dan
untuk MELIHAT struktur JSON respons (pakai --dump-json) bila skema berubah.

  pip install httpx

Endpoint (dikonfirmasi dari Network tab SIMT):
  GET https://simt.kemendikdasmen.go.id/api/search-sekolah-and-siswa?search=<kata kunci>
  - Cookie: already_filled=true ; Referer: https://simt.kemendikdasmen.go.id/
  - 'search' tunggal: boleh NISN ATAU nama peserta didik. Respons JSON.

Contoh:
  python cek_portofolio.py --nama "Gandi Lubis"
  python cek_portofolio.py --nisn 0051234567
  python cek_portofolio.py --nama "Gandi Lubis" --dump-json resp.json
  python cek_portofolio.py --search "Gandi Lubis" --json

Butuh koneksi internet saat dijalankan.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("cek_portofolio")

SIMT_BASE_URL = "https://simt.kemendikdasmen.go.id"
DEFAULT_PATH = "/api/search-sekolah-and-siswa"
DEFAULT_PARAM = "search"
DEFAULT_TIMEOUT = 12.0
MAX_RETRIES = 2
NAME_MATCH_THRESHOLD = 0.82

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _clean_nisn(nisn: str) -> str:
    return re.sub(r"[^0-9]", "", nisn or "")


def _iter_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


def _find_keyed_lists(obj: Any, pattern: str) -> list[list]:
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
    for k, v in d.items():
        if re.search(pattern, str(k), re.I) and isinstance(v, (str, int, float)):
            s = str(v).strip()
            if s:
                return s
    return ""


def _student_name(d: dict) -> str:
    for pat in (r"nama_siswa", r"nama_peserta", r"^nama$", r"student.*name", r"^name$"):
        val = _field(d, pat)
        if val:
            return val
    return _field(d, r"nama")


def _student_school(d: dict) -> str:
    return _field(d, r"sekolah|satuan_pendidikan|asal")


def _looks_like_student(d: dict) -> bool:
    if _field(d, r"nisn"):
        return True
    return bool(_student_name(d) and _student_school(d))


def _extract_students(data: Any) -> list[dict]:
    students: list[dict] = []
    for lst in _find_keyed_lists(data, r"siswa|peserta|student"):
        students.extend(x for x in lst if isinstance(x, dict))
    if students:
        return students
    return [d for d in _iter_dicts(data) if _looks_like_student(d)]


def _match_name(nama: str, students: list[dict]) -> tuple[bool, float]:
    target = _normalize(nama)
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


async def _fetch_json(url: str, timeout: float) -> Any:
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
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("fetch gagal (percobaan %d): %s", attempt, exc)
            await asyncio.sleep(0.6 * attempt)
    assert last_exc is not None
    raise last_exc


async def check_portfolio(
    nisn: str = "",
    nama: str = "",
    search: str = "",
    *,
    path: str = DEFAULT_PATH,
    param: str = DEFAULT_PARAM,
    timeout: float = DEFAULT_TIMEOUT,
    dump_json: str | None = None,
) -> dict[str, Any]:
    nisn_c, nama_c = _clean_nisn(nisn), nama.strip()
    # Tentukan kata kunci: --search eksplisit > NISN > nama.
    if search.strip():
        term, kunci = search.strip(), ("nisn" if search.strip().isdigit() else "nama")
    elif nisn_c:
        term, kunci = nisn_c, "nisn"
    else:
        term, kunci = nama_c, "nama"

    result: dict[str, Any] = {
        "checked": False, "terdaftar": None, "total_ditemukan": 0,
        "nisn_cocok": False, "nama_cocok": False, "skor_kecocokan_nama": 0.0,
        "kunci_pencarian": kunci, "nisn_query": nisn_c, "nama_query": nama_c,
        "kandidat": [], "sumber": None, "error": None,
    }
    if not term:
        result["error"] = "Tidak ada kata kunci (NISN/nama/search)."
        return result

    url = f"{SIMT_BASE_URL}{path}?{urlencode({param: term})}"
    result["sumber"] = url

    try:
        data = await _fetch_json(url, timeout)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Gagal mengakses SIMT: {exc}"
        return result

    if dump_json:
        with open(dump_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.warning("JSON mentah disimpan ke %s", dump_json)

    students = _extract_students(data)
    if not students and isinstance(data, dict):
        logger.warning("Struktur JSON tak dikenali; key teratas = %s", list(data.keys()))

    result["checked"] = True
    result["total_ditemukan"] = len(students)
    result["terdaftar"] = len(students) > 0
    result["kandidat"] = [
        {"nama": _student_name(s), "nisn": _clean_nisn(_field(s, r"nisn")),
         "sekolah": _student_school(s)}
        for s in students[:5]
    ]
    if nisn_c:
        result["nisn_cocok"] = any(
            _clean_nisn(_field(s, r"nisn")) == nisn_c for s in students
        )
    if nama_c:
        cocok, skor = _match_name(nama_c, students)
        result["nama_cocok"] = cocok
        result["skor_kecocokan_nama"] = round(skor, 3)
    return result


def _print_human(result: dict[str, Any]) -> None:
    print("=" * 60)
    print("HASIL CEK PORTOFOLIO PRESTASI - SIMT PUSPRESNAS")
    print("=" * 60)
    print(f"Kunci : {result.get('kunci_pencarian')}")
    print(f"NISN  : {result.get('nisn_query') or '-'}")
    print(f"Nama  : {result.get('nama_query') or '-'}")
    if not result.get("checked"):
        print(f"Status: GAGAL DIPERIKSA ({result.get('error')})")
    elif result.get("terdaftar"):
        print(f"Status: DITEMUKAN ({result.get('total_ditemukan')} hasil)")
        if result.get("nisn_query"):
            print(f"NISN cocok : {'YA' if result.get('nisn_cocok') else 'tidak'}")
        if result.get("nama_query"):
            cocok = "COCOK" if result.get("nama_cocok") else "tidak terkonfirmasi"
            print(f"Nama cocok : {cocok} (skor {result.get('skor_kecocokan_nama')})")
        for k in result.get("kandidat", []):
            print(f"  - {k['nama']} | NISN {k['nisn'] or '-'} | {k['sekolah'] or '-'}")
    else:
        print("Status: TIDAK DITEMUKAN (0 hasil) - indikasi tidak terdaftar")
    if result.get("sumber"):
        print(f"Sumber: {result.get('sumber')}")
    print("-" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cek portofolio prestasi ke SIMT PUSPRESNAS.")
    p.add_argument("--nisn", default="", help="NISN siswa (diutamakan)")
    p.add_argument("--nama", default="", help="Nama peserta")
    p.add_argument("--search", default="", help="Kata kunci mentah (override NISN/nama)")
    p.add_argument("--path", default=DEFAULT_PATH, help=f"Path API (default {DEFAULT_PATH})")
    p.add_argument("--param", default=DEFAULT_PARAM, help=f"Nama parameter (default {DEFAULT_PARAM})")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--dump-json", default=None, help="Simpan JSON mentah ke berkas untuk inspeksi")
    p.add_argument("--json", action="store_true", help="Cetak JSON saja")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if not args.nisn and not args.nama and not args.search:
        try:
            args.search = input("NISN / Nama peserta: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDibatalkan.")
            return 1
    result = asyncio.run(check_portfolio(
        nisn=args.nisn, nama=args.nama, search=args.search,
        path=args.path, param=args.param, timeout=args.timeout,
        dump_json=args.dump_json,
    ))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)
    return 0 if result.get("checked") else 2


if __name__ == "__main__":
    raise SystemExit(main())
