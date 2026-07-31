import json
import logging
import os

from llama_index.llms.google_genai import GoogleGenAI

from config import GOOGLE_API_KEY, today_str_id
from config import GEMINI_MODEL
from core.genai_utils import call_with_retry
from services.puspresnas import format_for_audit
from services.portfolio import format_for_audit_portfolio
from services.kurasi_lokal import format_for_audit_kurasi
from services.kriteria_lokal import format_for_audit_kriteria

logger = logging.getLogger("compliance.audit")

# temperature=0.0 -> keluaran deterministik (sebisanya) agar hasil evaluasi
# akurasi dapat direproduksi. JANGAN dinaikkan selama fase pengujian.
llm = GoogleGenAI(
    model=f"models/{GEMINI_MODEL}",
    api_key=GOOGLE_API_KEY,
    temperature=0.0,
)

# ---------------------------------------------------------------------------
# DESAIN SKOR & STATUS (deterministik, dihitung di Python -- BUKAN oleh LLM)
#
# Prinsip: LLM hanya MENALAR per kriteria dan mengeluarkan status tiga-nilai
# ('terpenuhi' / 'tidak_terpenuhi' / 'tidak_dapat_dinilai'). Angka skor dan
# status akhir diturunkan lewat tabel keputusan + bobot di bawah, sehingga
# skor dan status TIDAK MUNGKIN saling bertentangan (mis. "Ditolak" berskor 50).
#
# Bobot bersifat KEPUTUSAN DESAIN, dapat dikonfigurasi via env, dan perlu
# dikonfirmasi dengan pembimbing/pengguna. Total bobot harus = 1.0.
# ---------------------------------------------------------------------------
KRITERIA_LABELS = {
    "pencocokan_nama": "Pencocokan Nama",
    "anti_kecurangan": "Anti-Kecurangan",
    "relevansi_prestasi": "Relevansi Prestasi",
}

BOBOT_KRITERIA = {
    "pencocokan_nama": float(os.getenv("BOBOT_NAMA", "0.4")),
    "anti_kecurangan": float(os.getenv("BOBOT_FRAUD", "0.2")),
    "relevansi_prestasi": float(os.getenv("BOBOT_RELEVANSI", "0.4")),
}

POIN_HASIL = {
    "terpenuhi": 1.0,
    "tidak_dapat_dinilai": 0.5,
    "tidak_terpenuhi": 0.0,
}

_HASIL_VALID = set(POIN_HASIL)

# TIGA ZONA KEPUTUSAN (kebijakan pemilik sistem, revisi):
#   Ditolak otomatis  : HANYA kegagalan administratif keras -- nama pada
#                       sertifikat jelas orang lain (dan berkas bukan
#                       sertifikat, ditangani lebih hulu di agent).
#   Diterima otomatis : seluruh kriteria terpenuhi (termasuk relevansi
#                       TERCANTUM pada kriteria resmi prodi).
#   Abu-abu (manual)  : segala ketidakpastian -- termasuk SELURUH kasus
#                       jenis lomba TIDAK TERDAFTAR pada tingkat yang diakui.
#                       Keterkaitan bidang lomba dengan prodi dicatat sebagai
#                       INFORMASI bagi verifikator, TIDAK PERNAH menjadi dasar
#                       penolakan otomatis (kebijakan pemilik sistem, selaras
#                       praktik verifikator & rubrik yang menghargai bidang
#                       apa pun). Konsekuensi: false-reject turun, beban
#                       tinjauan manual naik.
# 'anti_kecurangan' tetap tidak pernah menolak otomatis (sinyal EXIF/QR
# bersifat indikatif).
_KRITERIA_KRITIS = ("pencocokan_nama", "relevansi_prestasi")


def _normalize_kriteria(raw: dict | None) -> dict:
    """Pastikan ketiga kriteria selalu ada dengan nilai hasil yang valid.

    Nilai tak dikenal / kriteria hilang dipetakan ke 'tidak_dapat_dinilai'
    (fail-safe: ketidakjelasan berujung tinjauan manusia, bukan keputusan).
    """
    kriteria: dict = {}
    raw = raw if isinstance(raw, dict) else {}
    for key in KRITERIA_LABELS:
        item = raw.get(key)
        item = item if isinstance(item, dict) else {}
        hasil = str(item.get("hasil", "")).strip().lower().replace(" ", "_")
        if hasil not in _HASIL_VALID:
            logger.warning("Kriteria '%s' bernilai tak dikenal: %r -> "
                           "tidak_dapat_dinilai", key, item.get("hasil"))
            hasil = "tidak_dapat_dinilai"
        alasan = str(item.get("alasan", "") or "").strip()
        kriteria[key] = {"hasil": hasil, "alasan": alasan}
    return kriteria


def _terapkan_kebijakan_relevansi(kriteria: dict, kriteria_resmi: dict | None) -> dict:
    """Sabuk pengaman deterministik (tidak bergantung kepatuhan model).

    Kebijakan pemilik sistem: hasil lookup 'lomba tidak terdaftar' (tingkat
    diakui) dan seluruh status 'ambigu' TIDAK PERNAH memvonis negatif --
    maksimal 'tidak_dapat_dinilai' sehingga tabel keputusan mengarahkannya
    ke tinjauan manual. Keterkaitan bidang hanyalah informasi.
    """
    if not kriteria_resmi:
        return kriteria
    sub = kriteria_resmi.get("sub_status")
    status = kriteria_resmi.get("status")
    if sub == "lomba_tidak_terdaftar" or status == "ambigu":
        rel = kriteria.get("relevansi_prestasi", {})
        if rel.get("hasil") == "tidak_terpenuhi":
            logger.info("Kebijakan relevansi: override 'tidak_terpenuhi' -> "
                        "'tidak_dapat_dinilai' (sub_status=%s, status=%s)", sub, status)
            rel["hasil"] = "tidak_dapat_dinilai"
            rel["alasan"] = ((rel.get("alasan", "") or "").strip() +
                             " [Kebijakan: jenis lomba tidak terdaftar pada daftar resmi "
                             "tidak ditolak otomatis; keterkaitan bidang dicatat sebagai "
                             "informasi dan keputusan akhir berada pada verifikator.]").strip()
            kriteria["relevansi_prestasi"] = rel
    return kriteria


def compute_verdict(kriteria: dict) -> dict:
    """Tabel keputusan + skor deterministik dari status per kriteria.

    Aturan status (urutan prioritas):
      1. Kriteria KRITIS (nama / relevansi) 'tidak_terpenuhi' -> Ditolak
      2. Ada kriteria 'tidak_dapat_dinilai',
         atau 'anti_kecurangan' == 'tidak_terpenuhi'      -> Butuh Tinjauan Manual
      3. Semua 'terpenuhi'                                -> Diterima

    Skor = 100 * sum(bobot_k * poin(hasil_k)); murni aritmetika, tanpa LLM.
    """
    hasil = {k: v["hasil"] for k, v in kriteria.items()}

    if any(hasil[k] == "tidak_terpenuhi" for k in _KRITERIA_KRITIS):
        status = "Ditolak"
    elif ("tidak_dapat_dinilai" in hasil.values()
          or hasil["anti_kecurangan"] == "tidak_terpenuhi"):
        status = "Butuh Tinjauan Manual"
    else:
        status = "Diterima"

    skor = round(100 * sum(
        BOBOT_KRITERIA[k] * POIN_HASIL[hasil[k]] for k in KRITERIA_LABELS
    ))

    gagal = [KRITERIA_LABELS[k] for k, h in hasil.items() if h == "tidak_terpenuhi"]
    perlu_cek = [KRITERIA_LABELS[k] for k, h in hasil.items()
                 if h == "tidak_dapat_dinilai"]
    if gagal or perlu_cek:
        bagian = []
        if gagal:
            bagian.append("Tidak terpenuhi: " + ", ".join(gagal))
        if perlu_cek:
            bagian.append("Tidak dapat dinilai otomatis: " + ", ".join(perlu_cek))
        langkah_gagal = ". ".join(bagian)
    else:
        langkah_gagal = None

    return {"status": status, "skor_kepatuhan": skor, "langkah_gagal": langkah_gagal}


def _compose_reasoning(kriteria: dict, verdict: dict, llm_reasoning: str) -> str:
    """Reasoning final: poin per kriteria dari LLM + kesimpulan dari tabel keputusan.

    Kesimpulan disusun dari verdict deterministik (bukan kalimat bebas LLM)
    agar narasi tidak pernah bertentangan dengan status/skor tersimpan.
    """
    if llm_reasoning and llm_reasoning.strip():
        body = llm_reasoning.strip()
    else:
        # Fallback: rakit dari alasan per kriteria bila LLM tidak memberi teks.
        lines = []
        for i, key in enumerate(KRITERIA_LABELS, start=1):
            item = kriteria[key]
            lines.append(
                f"{i}. **{KRITERIA_LABELS[key]}:** {item['alasan'] or '(tanpa alasan)'} "
                f"Status: {item['hasil'].replace('_', ' ')}."
            )
        body = "\n".join(lines)

    if verdict["status"] == "Diterima":
        kesimpulan = ("Seluruh kriteria terpenuhi; berkas direkomendasikan "
                      "DITERIMA (tetap menunggu konfirmasi verifikator).")
    elif verdict["status"] == "Ditolak":
        kesimpulan = (f"Berkas DITOLAK. {verdict['langkah_gagal']}.")
    else:
        kesimpulan = (f"Berkas membutuhkan TINJAUAN MANUAL. "
                      f"{verdict['langkah_gagal']}.")

    return f"{body}\n**Kesimpulan:** {kesimpulan}"


# ---------------------------------------------------------------------------
# Skema keluaran LLM: HANYA status + alasan per kriteria dan teks reasoning.
# TANPA field skor dan TANPA status akhir -- keduanya dihitung di Python.
# ---------------------------------------------------------------------------
_JSON_SCHEMA = '''{
    "kriteria": {
        "pencocokan_nama":    {"hasil": "terpenuhi | tidak_terpenuhi | tidak_dapat_dinilai", "alasan": "1-2 kalimat"},
        "anti_kecurangan":    {"hasil": "terpenuhi | tidak_terpenuhi | tidak_dapat_dinilai", "alasan": "1-2 kalimat"},
        "relevansi_prestasi": {"hasil": "terpenuhi | tidak_terpenuhi | tidak_dapat_dinilai", "alasan": "1-2 kalimat"}
    },
    "reasoning": "Poin bernomor markdown. WAJIB ikuti format: '1. **Pencocokan Nama:** ... 2. **Anti-Kecurangan:** ... 3. **Relevansi Prestasi:** ...'. Setiap poin menyebut status kriteria persis salah satu dari: terpenuhi / tidak terpenuhi / tidak dapat dinilai. JANGAN menulis baris Kesimpulan; kesimpulan disusun oleh sistem."
}'''

_ATURAN_TIGA_NILAI = (
    "ATURAN STATUS KRITERIA (WAJIB):\n"
    "- 'terpenuhi'            : bukti pada data JELAS mendukung kriteria.\n"
    "- 'tidak_terpenuhi'      : bukti pada data JELAS melanggar kriteria.\n"
    "- 'tidak_dapat_dinilai'  : data tidak cukup / ambigu / butuh sumber di luar\n"
    "  data yang diberikan. JANGAN memaksakan terpenuhi/tidak_terpenuhi bila\n"
    "  informasinya tidak tersedia -- pilih 'tidak_dapat_dinilai'.\n"
    "- JANGAN mengeluarkan skor angka atau status kelulusan akhir dalam bentuk\n"
    "  apa pun; keduanya dihitung oleh sistem, bukan oleh Anda."
)

_REASONING_FORMAT = (
    "FORMAT WAJIB UNTUK FIELD 'reasoning':\n"
    "- Daftar bernomor markdown, satu nomor per kriteria.\n"
    "- Setiap poin: '<nomor>. **<Label Kriteria>:** <penjelasan>'.\n"
    "- Label baku BERURUTAN: 'Pencocokan Nama', 'Anti-Kecurangan', "
    "'Relevansi Prestasi'.\n"
    "- Setiap poin menyatakan eksplisit: terpenuhi / tidak terpenuhi / "
    "tidak dapat dinilai (konsisten dengan field 'kriteria').\n"
    "- JANGAN menambahkan baris '**Kesimpulan:**' -- sistem yang menyusunnya.\n"
    "- JANGAN menulis 'reasoning' sebagai satu paragraf tanpa nomor."
)

# ---------------------------------------------------------------------------
# ATURAN RELEVANSI (KETAT) -- dipertahankan dari versi sebelumnya.
# ---------------------------------------------------------------------------
_RELEVANSI_RULE = (
    "ATURAN PENILAIAN 'Relevansi Prestasi' (WAJIB, KETAT):\n"
    "- SUMBER UTAMA relevansi adalah 'HASIL PENGECEKAN KRITERIA RESMI' di bawah "
    "-- lookup deterministik terhadap data kriteria resmi per prodi. IKUTI:\n"
    "  * TERCANTUM pada daftar resmi        -> WAJIB 'terpenuhi'.\n"
    "  * TIDAK TERCANTUM [SUB-JENIS: TINGKAT TIDAK DIAKUI PRODI] -> WAJIB "
    "'tidak_terpenuhi': prodi secara eksplisit tidak menerima prestasi pada "
    "tingkat tersebut; keterkaitan tema TIDAK menyelamatkan.\n"
    "  * TIDAK TERCANTUM [SUB-JENIS: JENIS LOMBA TIDAK TERDAFTAR] -> WAJIB "
    "'tidak_dapat_dinilai' (dieskalasi ke verifikator). Keterkaitan bidang "
    "lomba dengan prodi (bila ada) DISEBUT dalam alasan sebagai INFORMASI "
    "TAMBAHAN bagi verifikator, namun baik adanya maupun tiadanya keterkaitan "
    "TIDAK mengubah hasil: lomba yang tidak terdaftar TIDAK PERNAH ditolak "
    "otomatis.\n"
    "  * TIDAK DAPAT DIPUTUSKAN otomatis    -> nilai sendiri dari KONTEKS ATURAN "
    "(RAG); bila tetap tidak jelas -> 'tidak_dapat_dinilai'.\n"
    "- KONTEKS ATURAN (RAG) berfungsi sebagai pendukung naratif (definisi, "
    "ketentuan umum, sitasi) -- BUKAN pembatal hasil lookup resmi.\n"
    "- NORMALISASI TINGKAT: daftar aturan hanya mengenal tingkat Internasional, "
    "Nasional, Kabupaten/Kota, dan Lokal. Perlakukan tingkat 'Provinsi' (atau "
    "'tingkat provinsi', 'antar-kabupaten/kota se-provinsi', dsb.) SEBAGAI SETARA "
    "dengan tingkat 'Kabupaten/Kota'. Jadi bila suatu jenis lomba diakui pada "
    "tingkat Kabupaten/Kota untuk prodi tujuan, prestasi tingkat Provinsi pada "
    "jenis lomba yang sama DIANGGAP relevan/terpenuhi.\n"
    "- PENGUNCIAN TINGKAT: kecocokan dinilai pada pasangan (jenis lomba, tingkat "
    "PADA SERTIFIKAT). Nama/merek ajang yang dikenal berjenjang nasional (mis. "
    "OSN) TIDAK membuat sertifikat tingkat Kabupaten/Kota otomatis dihitung "
    "sebagai prestasi Nasional; gunakan tingkat yang tercetak pada sertifikat.\n"
    "- DILARANG menilai relevansi dari keterkaitan TEMA lomba dengan bidang studi. "
    "Prestasi OLAHRAGA, SENI, KEAGAMAAN, DEBAT, dsb. TETAP 'relevan/terpenuhi' "
    "selama jenis lomba tersebut tercantum dalam daftar prestasi yang diakui "
    "program studi tujuan. Contoh: O2SN, PON, PORSENI, FLS2N adalah prestasi SAH "
    "bila tercantum untuk prodi tersebut, meskipun prodinya teknik.\n"
    "- Cocokkan secara fleksibel: gunakan nama lomba, singkatan, DAN kategori. "
    "Perbedaan penulisan/edisi-tahun tidak membatalkan kecocokan.\n"
    "- 'terpenuhi' bila jenis lomba tercantum di daftar yang diakui pada tingkat "
    "yang sesuai; 'tidak_terpenuhi' HANYA bila benar-benar tidak tercantum pada "
    "tingkat manapun untuk prodi tujuan.\n"
    "- KESAMPINGKAN pemeriksaan JENJANG/JURUSAN ASAL SEKOLAH pendaftar "
    "(SMA/MA/SMK beserta rumpun jurusannya). JANGAN menjadikannya kriteria "
    "penilaian maupun poin bernomor pada 'reasoning'.\n"
    "- Bila KONTEKS ATURAN untuk prodi tujuan tidak memuat informasi yang cukup "
    "untuk menilai relevansi prestasi, gunakan 'tidak_dapat_dinilai' -- "
    "JANGAN menolak."
)


def _extract_json(text: str) -> dict:
    """Parsing JSON yang tahan terhadap pagar kode/teks tambahan dari LLM."""
    cleaned = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: ambil substring dari kurawal pertama hingga terakhir.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


async def run_audit(extracted: dict, target_major: str, expected_name: str,
                    fraud_flags: list, qr_data: list, rag_context: str,
                    puspresnas: dict | None = None,
                    portfolio: dict | None = None,
                    kurasi: dict | None = None,
                    kriteria_resmi: dict | None = None) -> dict:
    fraud_summary = fraud_flags if fraud_flags else "Tidak ada indikasi (tidak ada flag)"
    qr_summary = qr_data if qr_data else "Tidak ditemukan"
    # Utamakan hasil kurasi LOKAL (dari data scraping SIMT). Bila tidak ada,
    # jatuh ke pengecekan live PUSPRESNAS (bila dijalankan), lalu ke pesan default.
    if kurasi is not None:
        kurasi_summary = format_for_audit_kurasi(kurasi)
    elif puspresnas:
        kurasi_summary = format_for_audit(puspresnas)
    else:
        kurasi_summary = "Pengecekan kurasi SIMT tidak dijalankan."
    portfolio_summary = (
        format_for_audit_portfolio(portfolio) if portfolio
        else "Pengecekan portofolio prestasi tidak dijalankan."
    )
    hari_ini = today_str_id()
    prompt = f"""
Anda adalah Auditor Admisi POLBAN Berbasis AI.
Tugas Anda: nilai SETIAP kriteria di bawah berdasarkan data yang diberikan.
Anda TIDAK memutuskan lulus/tidaknya berkas dan TIDAK memberi skor -- itu
dihitung sistem dari status kriteria yang Anda keluarkan.

TANGGAL HARI INI: {hari_ini}.
ACUAN WAKTU (WAJIB DIPATUHI):
- Gunakan tanggal di atas sebagai "sekarang".
- Tanggal kegiatan SEBELUM atau SAMA DENGAN hari ini = kegiatan SUDAH terjadi
  dan SAH untuk dinilai. JANGAN menganggapnya "masa depan" hanya karena angka
  tahunnya terlihat besar (mis. 2025/2026).
- Tanggal kegiatan SETELAH hari ini = anomali temporal. Tandai
  'relevansi_prestasi' sebagai 'tidak_dapat_dinilai' dengan alasan menyebut
  tanggal tersebut, agar diperiksa verifikator manusia. JANGAN langsung
  menganggapnya pemalsuan, dan JANGAN pula mengabaikannya.

DATA PENDAFTAR:
{json.dumps(extracted, indent=2, ensure_ascii=False)}
JURUSAN TUJUAN: {target_major}
NAMA YANG DIHARAPKAN: {expected_name}

ATURAN 'Pencocokan Nama' (SANGAT PENTING!):
- Bandingkan "nama_peserta" dengan NAMA YANG DIHARAPKAN ("{expected_name}").
- Perbedaan kapitalisasi/gelar/urutan ringan = tetap 'terpenuhi'.
- Nama yang jelas berbeda orang = 'tidak_terpenuhi'.
- Nama pada sertifikat kosong/tak terbaca = 'tidak_dapat_dinilai'.

ATURAN 'Anti-Kecurangan':
- Flags: {fraud_summary}
- QR/Barcode: {qr_summary}
- Flags berbasis metadata (mis. jejak software desain seperti Canva/Photoshop)
  bersifat INDIKATIF, BUKAN bukti pemalsuan -- sertifikat resmi memang lazim
  dibuat penyelenggara dengan perangkat desain tersebut.
- Tidak ada flag = 'terpenuhi'. Ada flag metadata = 'tidak_dapat_dinilai'
  (serahkan ke verifikator) dengan alasan menyebut flag tersebut.
- 'tidak_terpenuhi' HANYA bila ada bukti kuat manipulasi konten (mis. teks
  pada dokumen tampak ditimpa/diedit secara kasat mata pada data ekstraksi).

HASIL PENGECEKAN KRITERIA RESMI (lookup deterministik data kriteria prodi):
{format_for_audit_kriteria(kriteria_resmi)}

{_RELEVANSI_RULE}

INFORMASI KURASI SIMT (dari pencocokan ke data resmi SIMT hasil scraping):
- Status kurasi ajang/penyelenggara: {kurasi_summary}
- Keaslian sertifikat (portofolio): {portfolio_summary}
CATATAN PENTING: Kedua poin di atas adalah PENANDA INFORMATIF untuk verifikator
manusia. JANGAN menjadikannya kriteria bernomor tersendiri dan JANGAN
menjadikannya dasar 'tidak_terpenuhi'. Anda BOLEH menyebut status kurasi
sebagai konteks pendukung di dalam poin 'Relevansi Prestasi'.

KONTEKS ATURAN (RAG) untuk program studi '{target_major}':
{rag_context}

{_ATURAN_TIGA_NILAI}

{_REASONING_FORMAT}

Output JSON murni (tanpa pagar kode):
{_JSON_SCHEMA}
"""
    response = await call_with_retry(
        lambda: llm.acomplete(prompt),
        what="Audit kepatuhan (Gemini)",
    )
    try:
        parsed = _extract_json(response.text)
    except json.JSONDecodeError as exc:
        logger.error("Audit mengembalikan non-JSON: %s", response.text[:200])
        raise ValueError(f"Audit model returned non-JSON: {response.text[:200]}") from exc

    kriteria = _normalize_kriteria(parsed.get("kriteria"))
    kriteria = _terapkan_kebijakan_relevansi(kriteria, kriteria_resmi)
    verdict = compute_verdict(kriteria)
    reasoning = _compose_reasoning(kriteria, verdict, parsed.get("reasoning", ""))

    # Kunci-kunci lama (status, skor_kepatuhan, langkah_gagal, reasoning)
    # dipertahankan agar agent.py & frontend tidak perlu diubah.
    return {
        "status": verdict["status"],
        "skor_kepatuhan": verdict["skor_kepatuhan"],
        "langkah_gagal": verdict["langkah_gagal"],
        "reasoning": reasoning,
        "kriteria": kriteria,  # detail per kriteria untuk API/log/evaluasi
    }
