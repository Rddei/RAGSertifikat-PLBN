import json
import logging

from google import genai as google_genai
from google.genai import types as genai_types

from config import GOOGLE_API_KEY
from core.genai_utils import call_with_retry

logger = logging.getLogger("compliance.vision")
vision_client = google_genai.Client(api_key=GOOGLE_API_KEY)

# ---------------------------------------------------------------------------
# Prompt ekstraksi terstruktur.
#
# Field dikelompokkan sesuai dimensi verifikasi:
#   - Legalitas ajang  : nama_lomba, singkatan_lomba, nama_penyelenggara,
#                        kategori, tingkat, tanggal
#   - Kualifikasi      : peringkat, tingkat
#   - Keaslian         : nomor_sertifikat, url_verifikasi, penandatangan,
#                        ada_cap, deskripsi_cap, ada_ttd
#   - Identitas        : nama_peserta
#
# Catatan penting:
#   - Model HANYA melaporkan APA YANG TERLIHAT; TIDAK menilai keaslian cap/ttd.
#   - Field yang tidak ditemukan diisi "" (string) atau false (boolean).
#   - NISN & asal_sekolah TIDAK diekstrak di sini karena jarang tercetak pada
#     sertifikat prestasi; keduanya diambil dari data pendaftaran (form).
# ---------------------------------------------------------------------------
_PROMPT = """
Anda adalah asisten ekstraksi data sertifikat prestasi. Perhatikan gambar/dokumen sertifikat ini dengan teliti, lalu ekstrak informasi ke dalam objek JSON
dengan kunci PERSIS sebagai berikut:

{
  "nama_peserta": "nama orang yang menerima/memenangkan sertifikat",
  "nama_lomba": "nama lengkap ajang/lomba/kompetisi",
  "singkatan_lomba": "akronim/singkatan lomba bila ada (mis. OSN, OLIVIA, KSN)",
  "nama_penyelenggara": "lembaga/instansi penyelenggara (lihat kop/logo)",
  "peringkat": "capaian: Juara 1/2/3, Medali Emas/Perak/Perunggu, Harapan, Finalis, dsb.",
  "tingkat": "salah satu: Internasional, Nasional, Provinsi, Kabupaten/Kota, Lokal. Kosongkan bila tidak tertulis eksplisit",
  "kategori": "bidang/cabang lomba (mis. Olahraga, Riset dan Inovasi, Seni Budaya, Matematika)",
  "tanggal": "tanggal atau tahun penyelenggaraan/penerbitan sebagaimana tercetak",
  "nomor_sertifikat": "nomor sertifikat/nomor SK bila tercetak",
  "url_verifikasi": "alamat URL verifikasi yang tercetak sebagai teks bila ada",
  "penandatangan": "nama penandatangan beserta jabatannya bila ada",
  "ada_cap": true/false,
  "deskripsi_cap": "deskripsi singkat cap/stempel yang terlihat (bentuk, warna, teks yang terbaca). Kosongkan bila tidak ada",
  "ada_ttd": true/false
}

ATURAN:
- Jika sebuah nilai teks tidak ditemukan, isi dengan string kosong "".
- Untuk "ada_cap" dan "ada_ttd", jawab HANYA dengan nilai boolean true atau false
  berdasarkan apa yang benar-benar TERLIHAT pada dokumen.
- Anda HANYA melaporkan apa yang terlihat. JANGAN menilai apakah cap/tanda tangan
  asli atau palsu, dan JANGAN mengarang teks cap yang tidak terbaca jelas.
- Jangan berikan teks tambahan, penjelasan, atau markdown. Keluarkan JSON saja.
"""


def _parse_json(text: str) -> dict:
    raw = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return json.loads(raw)


# Nilai default agar hasil ekstraksi selalu punya bentuk yang konsisten,
# meskipun model melewatkan sebagian field.
_DEFAULTS: dict = {
    "nama_peserta": "",
    "nama_lomba": "",
    "singkatan_lomba": "",
    "nama_penyelenggara": "",
    "peringkat": "",
    "tingkat": "",
    "kategori": "",
    "tanggal": "",
    "nomor_sertifikat": "",
    "url_verifikasi": "",
    "penandatangan": "",
    "ada_cap": False,
    "deskripsi_cap": "",
    "ada_ttd": False,
}


def _normalize_result(data: dict) -> dict:
    """Gabungkan hasil model dengan default agar semua field selalu ada."""
    result = dict(_DEFAULTS)
    if isinstance(data, dict):
        for key in _DEFAULTS:
            if key in data and data[key] is not None:
                result[key] = data[key]
    # Pastikan tipe boolean untuk field pemeriksaan cap/ttd.
    for bkey in ("ada_cap", "ada_ttd"):
        result[bkey] = bool(result[bkey]) if not isinstance(result[bkey], str) \
            else result[bkey].strip().lower() in ("true", "ya", "1", "ada")
    return result


async def extract_certificate_data(image_bytes: bytes, mime_type: str) -> dict:
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = await call_with_retry(
        lambda: vision_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[_PROMPT, image_part],
            # Paksa keluaran berupa JSON -> mengurangi parsing yang rapuh.
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        ),
        what="Ekstraksi data sertifikat (Gemini Vision)",
    )
    try:
        parsed = _parse_json(response.text)
    except json.JSONDecodeError as exc:
        logger.error("Vision mengembalikan non-JSON: %s", response.text[:200])
        raise ValueError(f"Vision model returned non-JSON: {response.text[:200]}") from exc
    return _normalize_result(parsed)
