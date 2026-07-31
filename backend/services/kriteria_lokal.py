"""
Pengecekan RELEVANSI PRESTASI secara deterministik terhadap data kriteria
resmi per program studi (hasil pembersihan sheet "Data Lengkap Prodi SNBP").

Peran modul ini dalam arsitektur hybrid:
  - Kriteria TERSTRUKTUR (jenis lomba yang diakui per prodi per tingkat)
    dinilai lewat LOOKUP pada data resmi -> hasilnya FAKTA bagi auditor LLM.
  - RAG tetap memasok ketentuan NARATIF pedoman (definisi, pengecualian,
    sitasi) sebagai konteks pendukung -- bukan penentu relevansi.

Kontrak (meniru kurasi_lokal): fungsi TIDAK melempar exception ke pipeline;
segala kegagalan menghasilkan status 'ambigu' agar berujung tinjauan manusia.
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache

logger = logging.getLogger("compliance.kriteria")

KRITERIA_JSON_PATH = os.getenv("KRITERIA_JSON_PATH", "data/kriteria_prodi.json")
# Ambang kemiripan nama lomba terhadap item daftar resmi.
KRITERIA_NAME_THRESHOLD = float(os.getenv("KRITERIA_NAME_THRESHOLD", "0.82"))

# Kelas prestasi GENERIK pada daftar resmi (bukan nama ajang spesifik).
# Dicocokkan lewat kata kunci pada kategori/nama lomba sertifikat.
_KELAS_GENERIK: dict[str, set[str]] = {
    "olahraga": {
        "olahraga", "o2sn", "pon", "porda", "porprov", "porseni", "popda",
        "sepak", "futsal", "basket", "voli", "badminton", "bulu tangkis",
        "bulutangkis", "silat", "pencak", "karate", "taekwondo", "judo",
        "renang", "atletik", "lari", "catur", "panahan", "tenis", "senam",
    },
    "seni": {
        "seni", "fls2n", "tari", "musik", "vokal", "menyanyi", "paduan suara",
        "lukis", "melukis", "gambar", "teater", "puisi", "kaligrafi seni",
        "band", "fotografi", "film", "desain grafis",
    },
    "keagamaan": {
        "keagamaan", "agama", "mtq", "musabaqah", "tilawah", "tahfidz",
        "tahfiz", "hifzil", "qur", "dai", "da'i", "adzan", "azan",
        "kaligrafi islam", "nasyid", "cerdas cermat agama", "pai",
    },
}

_TINGKAT_MAP = [
    (("internasional", "international"), "Internasional"),
    (("nasional", "national"), "Nasional"),
    # Kebijakan resmi: tingkat Provinsi diperlakukan setara Kabupaten/Kota.
    (("provinsi", "prov ", "se-provinsi"), "Kabupaten/Kota"),
    (("kabupaten", "kab.", "kab/", "kota", "kab-kota", "kabupaten/kota"), "Kabupaten/Kota"),
    (("lokal", "sekolah", "kecamatan", "internal"), "Lokal"),
]

# Hierarki tingkat prestasi, tertinggi -> terendah. Dipakai oleh aturan
# "dominasi ke atas": prestasi pada tingkat lebih tinggi tidak boleh dinilai
# lebih rendah daripada prestasi sejenis pada tingkat di bawahnya.
_TINGKAT_HIERARKI = ["Internasional", "Nasional", "Kabupaten/Kota", "Lokal"]


def _tingkat_lebih_rendah(t_norm: str) -> list[str]:
    """Daftar tingkat DI BAWAH t_norm, berurutan dari yang terdekat."""
    try:
        i = _TINGKAT_HIERARKI.index(t_norm)
    except ValueError:
        return []
    return _TINGKAT_HIERARKI[i + 1:]


_JENJANG_PAT = [
    (re.compile(r"\b(d[- ]?4|diploma\s*4|sarjana\s*terapan|s\.?tr)\b", re.I), "D4"),
    (re.compile(r"\b(d[- ]?3|diploma\s*3|ahli\s*madya)\b", re.I), "D3"),
]


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _acronym_of(item: str) -> str:
    """Ambil akronim dalam kurung, mis. 'Olimpiade Sains Nasional (OSN)' -> 'osn'."""
    m = re.search(r"\(([^)]+)\)", item)
    return _norm(m.group(1)) if m else ""


def _base_name(item: str) -> str:
    """Nama item tanpa bagian kurung."""
    return _norm(re.sub(r"\([^)]*\)", " ", item))


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    try:
        with open(KRITERIA_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        entri = data.get("entri", [])
        logger.info("Kriteria prodi dimuat: %d entri dari %s",
                    len(entri), KRITERIA_JSON_PATH)
        return entri
    except Exception:
        logger.exception("Gagal memuat kriteria prodi dari %s", KRITERIA_JSON_PATH)
        return []


def _normalize_tingkat(tingkat: str) -> str | None:
    t = _norm(tingkat)
    if not t:
        return None
    for keys, val in _TINGKAT_MAP:
        if any(k.strip() in t for k in keys):
            return val
    return None


def _resolve_prodi(target_major: str) -> tuple[dict | None, str]:
    """Cocokkan string jurusan tujuan aplikasi ke entri prodi (jenjang-aware).

    Nama prodi bisa sama di D3 dan D4 (mis. Teknik Informatika), sehingga
    jenjang pada input menentukan. Tanpa jenjang: hanya cocok bila tunggal.
    """
    entri = _load()
    if not entri:
        return None, "data kriteria tidak termuat"

    jenjang = None
    for pat, val in _JENJANG_PAT:
        if pat.search(target_major or ""):
            jenjang = val
            break
    n_target = _norm(re.sub(r"\b(d[- ]?[34]|diploma\s*[34]|sarjana\s*terapan)\b",
                            " ", target_major or "", flags=re.I))

    kandidat = []
    for e in entri:
        n_prodi = _norm(e["prodi"])
        skor = SequenceMatcher(None, n_target, n_prodi).ratio()
        if n_prodi and (n_prodi in n_target or n_target in n_prodi):
            skor = max(skor, 0.92)
        if skor >= 0.85:
            kandidat.append((skor, e))
    if not kandidat:
        return None, f"prodi '{target_major}' tidak ditemukan pada data kriteria"

    if jenjang:
        berjenjang = [(s, e) for s, e in kandidat if e["jenjang"] == jenjang]
        if berjenjang:
            kandidat = berjenjang
        else:
            return None, (f"prodi cocok ditemukan namun tidak pada jenjang "
                          f"{jenjang} sesuai input '{target_major}'")
    kandidat.sort(key=lambda x: -x[0])
    # Tanpa jenjang eksplisit: bila skor teratas dimiliki >1 jenjang, ambigu.
    if not jenjang:
        top = [e for s, e in kandidat if abs(s - kandidat[0][0]) < 1e-9]
        if len({e["jenjang"] for e in top}) > 1:
            return None, (f"prodi '{target_major}' ada di lebih dari satu "
                          f"jenjang (D3/D4); sebutkan jenjang pada jurusan tujuan")
    return kandidat[0][1], ""


def _match_item(item: str, n_nama: str, n_singkatan: str, n_kategori: str) -> float:
    """Skor kecocokan satu item daftar resmi terhadap data sertifikat."""
    n_item_base = _base_name(item)
    n_item_full = _norm(item)
    acr = _acronym_of(item)

    # Kelas generik (Olahraga/Seni/Keagamaan): cocokkan via kata kunci.
    if n_item_full in _KELAS_GENERIK:
        kws = _KELAS_GENERIK[n_item_full]
        haystack = f"{n_kategori} {n_nama}"
        if any(kw in haystack for kw in kws):
            return 0.93
        return 0.0

    best = 0.0
    if acr and n_singkatan and acr == n_singkatan:
        best = max(best, 0.95)
    for n_item in (n_item_base, n_item_full):
        if not n_item:
            continue
        if n_nama and (n_item in n_nama or n_nama in n_item):
            best = max(best, 0.90)
        if n_nama:
            best = max(best, SequenceMatcher(None, n_nama, n_item).ratio())
    if acr and n_nama and acr in n_nama.split():
        best = max(best, 0.88)
    return best


def check_relevansi(target_major: str, nama_lomba: str, singkatan: str,
                    kategori: str, tingkat: str) -> dict:
    """Lookup deterministik: apakah (jenis lomba, tingkat) diakui prodi tujuan.

    Status keluaran:
      'tercantum'       -> jenis lomba ada di daftar resmi pada tingkat tsb.
      'tidak_tercantum' -> tingkat tidak diakui prodi, ATAU jenis lomba tidak
                           ada pada daftar tingkat tsb.
      'ambigu'          -> data tidak cukup untuk memutuskan (prodi tak
                           terpetakan, tingkat kosong, daftar kosong, dst.)
                           -> auditor mengarah ke tinjauan manual.
    """
    hasil = {
        "status": "ambigu", "sub_status": None, "prodi": None, "jenjang": None,
        "tingkat_normal": None, "item_cocok": None, "skor": 0.0,
        "item_terdekat": None, "alasan": "",
    }
    try:
        prodi, err = _resolve_prodi(target_major)
        if prodi is None:
            hasil["alasan"] = err
            return hasil
        hasil["prodi"] = prodi["prodi"]
        hasil["jenjang"] = prodi["jenjang"]

        t_norm = _normalize_tingkat(tingkat)
        hasil["tingkat_normal"] = t_norm
        if t_norm is None:
            hasil["alasan"] = ("tingkat pada sertifikat kosong/tidak dikenali "
                               "sehingga relevansi tidak dapat diputuskan otomatis")
            return hasil

        diakui = {("Kabupaten/Kota" if "provinsi" in _norm(x) else
                   _normalize_tingkat(x) or x) for x in prodi["tingkat_diakui"]}
        if t_norm not in diakui:
            hasil["status"] = "tidak_tercantum"
            hasil["sub_status"] = "tingkat_tidak_diakui"
            hasil["alasan"] = (f"tingkat {t_norm} tidak termasuk tingkat prestasi "
                               f"yang diakui prodi {prodi['prodi']} "
                               f"({', '.join(sorted(diakui))})")
            return hasil

        if t_norm == "Lokal":
            hasil["alasan"] = ("tingkat Lokal diakui prodi, namun rincian jenis "
                               "lomba tingkat Lokal tidak tersedia pada data "
                               "kriteria; perlu tinjauan manual")
            return hasil

        daftar = prodi["prestasi"].get(t_norm, [])
        if not daftar:
            hasil["alasan"] = (f"daftar prestasi tingkat {t_norm} untuk prodi "
                               f"{prodi['prodi']} kosong pada data kriteria")
            return hasil

        n_nama = _norm(nama_lomba)
        n_singkatan = _norm(singkatan)
        n_kategori = _norm(kategori)
        skor_terbaik, item_terbaik = 0.0, None
        for item in daftar:
            s = _match_item(item, n_nama, n_singkatan, n_kategori)
            if s > skor_terbaik:
                skor_terbaik, item_terbaik = s, item

        hasil["skor"] = round(skor_terbaik, 3)
        hasil["item_terdekat"] = item_terbaik
        if skor_terbaik >= KRITERIA_NAME_THRESHOLD:
            hasil["status"] = "tercantum"
            hasil["item_cocok"] = item_terbaik
            hasil["alasan"] = (f"'{nama_lomba}' cocok dengan item resmi "
                               f"'{item_terbaik}' (skor {hasil['skor']}) pada "
                               f"tingkat {t_norm} prodi {prodi['prodi']}")
        else:
            # --- Aturan dominasi ke atas -----------------------------------
            # Jenis lomba tidak tercantum pada tingkat sertifikat, TETAPI
            # tercantum pada tingkat yang LEBIH RENDAH untuk prodi yang sama.
            # Menolak kasus ini tidak masuk akal: prestasi sejenis pada
            # tingkat lebih tinggi mustahil bernilai lebih rendah daripada
            # yang di bawahnya. Karena tidak tercantum secara harfiah, kasus
            # ini TIDAK diklaim tercantum, melainkan dieskalasi ke tinjauan
            # manusia (status 'ambigu'). Aturan sengaja SATU ARAH: tidak
            # berlaku sebaliknya (tercantum di atas, sertifikat di bawah).
            for t_bawah in _tingkat_lebih_rendah(t_norm):
                daftar_bawah = prodi["prestasi"].get(t_bawah, [])
                if not daftar_bawah:
                    continue
                skor_b, item_b = 0.0, None
                for item in daftar_bawah:
                    sb = _match_item(item, n_nama, n_singkatan, n_kategori)
                    if sb > skor_b:
                        skor_b, item_b = sb, item
                if skor_b >= KRITERIA_NAME_THRESHOLD:
                    hasil["status"] = "ambigu"
                    hasil["sub_status"] = "tercantum_tingkat_lebih_rendah"
                    hasil["item_terdekat"] = item_b
                    hasil["skor"] = round(skor_b, 3)
                    hasil["alasan"] = (
                        f"'{nama_lomba}' tidak tercantum pada daftar tingkat "
                        f"{t_norm}, namun jenis lomba sepadan ('{item_b}', skor "
                        f"{hasil['skor']}) TERCANTUM pada tingkat {t_bawah} "
                        f"untuk prodi {prodi['prodi']}. Karena tingkat "
                        f"{t_norm} lebih tinggi daripada {t_bawah}, prestasi "
                        f"ini tidak dapat dinyatakan tidak relevan secara "
                        f"otomatis dan diarahkan ke tinjauan manual"
                    )
                    return hasil

            hasil["status"] = "tidak_tercantum"
            hasil["sub_status"] = "lomba_tidak_terdaftar"
            hasil["alasan"] = (f"'{nama_lomba}' (tingkat {t_norm}) tidak "
                               f"ditemukan pada daftar prestasi yang diakui "
                               f"prodi {prodi['prodi']}; item terdekat: "
                               f"'{item_terbaik}' skor {hasil['skor']}")
        return hasil
    except Exception:
        logger.exception("check_relevansi gagal (fail-safe -> ambigu)")
        hasil["alasan"] = "kesalahan internal pengecekan kriteria"
        return hasil


def format_for_audit_kriteria(res: dict) -> str:
    """Ringkasan hasil lookup untuk disuntikkan ke prompt auditor."""
    if not res:
        return "Pengecekan kriteria resmi tidak dijalankan."
    label = {"tercantum": "TERCANTUM pada daftar resmi",
             "tidak_tercantum": "TIDAK TERCANTUM pada daftar resmi",
             "ambigu": "TIDAK DAPAT DIPUTUSKAN otomatis"}
    sub = {"tingkat_tidak_diakui": " [SUB-JENIS: TINGKAT TIDAK DIAKUI PRODI]",
           "lomba_tidak_terdaftar": " [SUB-JENIS: JENIS LOMBA TIDAK TERDAFTAR]",
           "tercantum_tingkat_lebih_rendah":
               " [SUB-JENIS: SEPADAN PADA TINGKAT LEBIH RENDAH -> ARAHKAN KE TINJAUAN]"}
    return (f"{label.get(res['status'], res['status'])}"
            f"{sub.get(res.get('sub_status'), '')}. "
            f"{res.get('alasan', '')}").strip()
