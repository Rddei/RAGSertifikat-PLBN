from google import genai as google_genai
from google.genai import types as genai_types
import json

from config import GOOGLE_API_KEY

vision_client = google_genai.Client(api_key=GOOGLE_API_KEY)

async def extract_certificate_data(image_bytes: bytes, mime_type: str) -> dict:
    prompt = """
    Anda adalah asisten ekstraksi data. Perhatikan gambar sertifikat ini.
    Ekstrak data ke dalam format JSON murni:
    {
        "nama_peserta": "...",
        "jenjang_sekolah": "...",
        "nama_lomba": "...",
        "nama_penyelenggara": "..."
    }
    Jangan berikan teks tambahan atau markdown.
    """
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = await vision_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, image_part]
    )
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Vision model returned non-JSON: {raw[:200]}") from exc