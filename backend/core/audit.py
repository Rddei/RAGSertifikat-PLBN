import json
from llama_index.llms.google_genai import GoogleGenAI
from config import GOOGLE_API_KEY

llm = GoogleGenAI(model="models/gemini-2.5-flash", api_key=GOOGLE_API_KEY)

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
    {{
        "status": "Diterima / Ditolak / Butuh Tinjauan Manual",
        "skor_kepatuhan": 0-100,
        "langkah_gagal": "Sebutkan langkah yang tidak terpenuhi, atau null",
        "reasoning": "Penjelasan detail, sertakan pencocokan nama."
    }}
    """
    response = await llm.acomplete(prompt)
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Audit model returned non-JSON: {raw[:200]}") from exc