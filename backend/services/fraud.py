# services/fraud.py
import io
from PIL import Image
from PIL.ExifTags import TAGS
from pyzbar.pyzbar import decode as decode_qr

def scan_for_fraud(image_bytes: bytes) -> tuple[list[str], list[str]]:
    fraud_flags = []
    qr_data = []
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name in ("Software", "ProcessingSoftware"):
                    val_lower = str(value).lower()
                    if any(kw in val_lower for kw in ("adobe", "photoshop", "canva")):
                        fraud_flags.append(f"Terindikasi editan software: {value}")
        for obj in decode_qr(img):
            qr_data.append(obj.data.decode("utf-8"))
    except Exception as e:
        print(f"Fraud scan error: {e}")
    return fraud_flags, qr_data