import json
import logging

from llama_index.llms.google_genai import GoogleGenAI

from config import GOOGLE_API_KEY

logger = logging.getLogger("compliance.audit")
llm = GoogleGenAI(model="models/gemini-2.5-flash", api_key=GOOGLE_API_KEY)

# Contoh format keluaran JSON (string biasa, bukan f-string)
_JSON_SCHEMA = '''{
    "status": "Diterima / Ditolak / Butuh Tinjauan Manual",
    "skor_kepatuhan": 0-100,
    "langkah_gagal": "Sebutkan langkah yang tidak terpenuhi, atau null",
    "reasoning": "Penjelasan detail, sertakan pencocokan nama."
}'''


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

Output JSON murni:
{_JSON_SCHEMA}
"""
    response = await llm.acomplete(prompt)
    try:
        return _extract_json(response.text)
    except json.JSONDecodeError as exc:
        logger.error("Audit mengembalikan non-JSON: %s", response.text[:200])
        raise ValueError(f"Audit model returned non-JSON: {response.text[:200]}") from exc
