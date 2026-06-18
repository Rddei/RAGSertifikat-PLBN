import json
import logging

from llama_index.llms.google_genai import GoogleGenAI

from config import GOOGLE_API_KEY
from core.genai_utils import call_with_retry

logger = logging.getLogger("compliance.audit")
llm = GoogleGenAI(model="models/gemini-2.5-flash", api_key=GOOGLE_API_KEY)

# Contoh format keluaran JSON (string biasa, bukan f-string)
_JSON_SCHEMA = '''{
    "status": "Diterima / Ditolak / Butuh Tinjauan Manual",
    "skor_kepatuhan": 0-100,
    "langkah_gagal": "Sebutkan langkah yang tidak terpenuhi, atau null",
    "reasoning": "Poin bernomor markdown. WAJIB ikuti format ini PERSIS: '1. **Pencocokan Nama:** ... 2. **Anti-Kecurangan:** ... 3. **Relevansi Prestasi:** ...' lalu akhiri dengan '**Kesimpulan:** ...'. Setiap kriteria diawali nomor lalu label tebal diakhiri titik dua. Selalu sebutkan status tiap kriteria dengan kata 'terpenuhi' / 'tidak terpenuhi'."
}'''

# Aturan format alasan, ditegaskan terpisah agar LLM patuh.
_REASONING_FORMAT = (
    "FORMAT WAJIB UNTUK FIELD 'reasoning':\n"
    "- Tulis sebagai daftar bernomor markdown, satu nomor per kriteria.\n"
    "- Setiap poin: '<nomor>. **<Label Kriteria>:** <penjelasan>'.\n"
    "- Gunakan label baku: 'Pencocokan Nama', 'Anti-Kecurangan', 'Relevansi Prestasi', "
    "dan 'Kesesuaian Jurusan' (bila relevan).\n"
    "- Untuk setiap kriteria, nyatakan eksplisit 'terpenuhi' atau 'tidak terpenuhi'.\n"
    "- Akhiri dengan satu baris '**Kesimpulan:** <ringkasan keputusan>'.\n"
    "- JANGAN menulis 'reasoning' sebagai satu paragraf tanpa nomor."
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
                    fraud_flags: list, qr_data: list, rag_context: str) -> dict:
    fraud_summary = fraud_flags if fraud_flags else "Bersih"
    qr_summary = qr_data if qr_data else "Tidak ditemukan"
    prompt = f"""
Anda adalah Auditor Admisi POLBAN Berbasis AI.
Tugas Anda: Berikan penilaian kelayakan berdasarkan data berikut.

DATA PENDAFTAR:
{json.dumps(extracted, indent=2, ensure_ascii=False)}
JURUSAN TUJUAN: {target_major}
NAMA YANG DIHARAPKAN: {expected_name}

ATURAN VALIDASI NAMA (SANGAT PENTING!):
- Bandingkan "nama_peserta" dengan NAMA YANG DIHARAPKAN ("{expected_name}").
- Jika berbeda jauh, status HARUS "Ditolak".

ANTI-KECURANGAN:
- Flags: {fraud_summary}
- QR/Barcode: {qr_summary}
(Jika Flags menunjukkan indikasi editan, WAJIB Ditolak skor 0)

KONTEKS ATURAN (RAG):
{rag_context}

{_REASONING_FORMAT}

Output JSON murni (tanpa pagar kode):
{_JSON_SCHEMA}
"""
    response = await call_with_retry(
        lambda: llm.acomplete(prompt),
        what="Audit kepatuhan (Gemini)",
    )
    try:
        return _extract_json(response.text)
    except json.JSONDecodeError as exc:
        logger.error("Audit mengembalikan non-JSON: %s", response.text[:200])
        raise ValueError(f"Audit model returned non-JSON: {response.text[:200]}") from exc
