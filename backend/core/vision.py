import json
import logging

from google import genai as google_genai
from google.genai import types as genai_types

from config import GOOGLE_API_KEY
from config import GEMINI_MODEL
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
  "jenis_sertifikat": "klasifikasikan dokumen ini BERDASARKAN APA YANG TERCETAK, pilih PERSIS SATU dari: 'prestasi_lomba' (ada lomba/kejuaraan/kompetisi DAN pencapaian peringkat seperti juara/medali/finalis), 'partisipasi' (hanya menyatakan keikutsertaan/telah mengikuti, TANPA peringkat), 'kursus_pelatihan' (penyelesaian kursus/pelatihan/workshop/webinar/bootcamp/course), 'penghargaan_non_lomba' (apresiasi tanpa kompetisi, mis. siswa terbaik, siswa teladan, penghargaan sekolah), 'bukan_sertifikat' (dokumen bukan sertifikat sama sekali), 'tidak_dapat_ditentukan' (bukti tercetak tidak cukup untuk memilih salah satu di atas)",
  "nama_peserta": "nama orang yang menerima/memenangkan sertifikat",
  "nama_lomba": "nama lengkap ajang/lomba/kompetisi",
  "singkatan_lomba": "akronim/singkatan lomba bila ada (mis. OSN, OLIVIA, KSN)",
  "nama_penyelenggara": "SATU instansi/lembaga PENYELENGGARA UTAMA kegiatan -- pihak yang MENYELENGGARAKAN lomba, BUKAN pihak yang menandatangani atau menerbitkan sertifikat. Pilih satu penyelenggara utama dengan urutan prioritas sumber: (1) frasa 'diselenggarakan oleh ...' pada badan sertifikat, (2) instansi pada kop/logo utama. ABAIKAN instansi yang hanya muncul di blok tanda tangan -- itu penandatangan/validator, bukan penyelenggara, dan sudah ditangkap pada field 'penandatangan'. JANGAN menggabungkan beberapa instansi dengan koma; pilih SATU yang paling jelas sebagai penyelenggara. Label kepanitiaan (mis. 'Panitia Kejuaraan X') hanya bila tidak ada sumber instansi lain",
  "peringkat": "capaian: Juara 1/2/3, Medali Emas/Perak/Perunggu, Harapan, Finalis, dsb.",
  "tingkat": "salah satu: Internasional, Nasional, Provinsi, Kabupaten/Kota, Lokal. Kosongkan bila tidak tertulis eksplisit",
  "kategori": "bidang/cabang lomba (mis. Olahraga, Riset dan Inovasi, Seni Budaya, Matematika)",
  "tanggal_pelaksanaan": "tanggal/rentang/tahun PELAKSANAAN kegiatan sebagaimana tercetak (biasanya pada badan sertifikat; bisa berupa rentang, mis. '17 - 18 Juli 2025'). Kosongkan bila tidak tercetak",
  "tanggal_terbit": "tanggal PENERBITAN sertifikat bila tercetak terpisah (lazim di dekat blok tanda tangan, format 'Kota, tanggal'). Kosongkan bila tidak ada. Bila hanya SATU tanggal tercetak dan konteksnya tidak jelas, isikan ke tanggal_pelaksanaan dan biarkan field ini kosong -- JANGAN menduplikasi",
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
- "jenis_sertifikat" WAJIB diisi salah satu nilai yang terdaftar, ditulis persis
  (huruf kecil, garis bawah). Dasarkan HANYA pada teks yang tercetak: adanya kata
  lomba/kompetisi/kejuaraan beserta peringkat menandai 'prestasi_lomba'; kata
  "telah mengikuti/berpartisipasi" tanpa peringkat menandai 'partisipasi'; kata
  kursus/pelatihan/workshop/webinar menandai 'kursus_pelatihan'.
- Bila ragu antara dua kelas, JANGAN menebak: pilih 'tidak_dapat_ditentukan'.
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
    # Default sengaja "tidak_dapat_ditentukan": bila model lalai mengisi,
    # berkas TIDAK ditolak otomatis melainkan lanjut ke pipeline penuh.
    "jenis_sertifikat": "tidak_dapat_ditentukan",
    "nama_peserta": "",
    "nama_lomba": "",
    "singkatan_lomba": "",
    "nama_penyelenggara": "",
    "peringkat": "",
    "tingkat": "",
    "kategori": "",
    "tanggal_pelaksanaan": "",
    "tanggal_terbit": "",
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
    # Pastikan field teks selalu berupa string rapi. Model kadang mengembalikan
    # list/objek (mis. deskripsi_cap atau penandatangan) yang bila disimpan apa
    # adanya membuat tampilan "ngebug" (muncul tanda kurung/kutip list). Ratakan
    # jadi string dipisah "; " agar konsisten dengan render di frontend.
    for skey in _DEFAULTS:
        if skey in ("ada_cap", "ada_ttd"):
            continue
        val = result[skey]
        if isinstance(val, list):
            result[skey] = "; ".join(str(x).strip() for x in val if str(x).strip())
        elif isinstance(val, dict):
            result[skey] = "; ".join(
                str(v).strip() for v in val.values() if str(v).strip()
            )
        elif not isinstance(val, str):
            result[skey] = str(val) if val is not None else ""
        else:
            result[skey] = val.strip()
    return result


async def extract_certificate_data(image_bytes: bytes, mime_type: str) -> dict:
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = await call_with_retry(
        lambda: vision_client.aio.models.generate_content(
            model=GEMINI_MODEL,
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