import json
import logging

from google import genai as google_genai
from google.genai import types as genai_types

from config import GOOGLE_API_KEY
from core.genai_utils import call_with_retry

logger = logging.getLogger("compliance.vision")
vision_client = google_genai.Client(api_key=GOOGLE_API_KEY)

_PROMPT = """
Anda adalah asisten ekstraksi data. Perhatikan gambar sertifikat ini.
Ekstrak data dengan kunci JSON: nama_peserta, nisn, asal_sekolah, jenjang_sekolah,
nama_lomba, nama_penyelenggara. Jika sebuah nilai tidak ditemukan, isi dengan string
kosong. Khusus "nisn": tuliskan hanya digit (Nomor Induk Siswa Nasional, biasanya 10
digit) bila tercetak pada sertifikat; "asal_sekolah": nama sekolah/instansi peserta.
Jangan berikan teks tambahan atau markdown.
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
        return _parse_json(response.text)
    except json.JSONDecodeError as exc:
        logger.error("Vision mengembalikan non-JSON: %s", response.text[:200])
        raise ValueError(f"Vision model returned non-JSON: {response.text[:200]}") from exc
