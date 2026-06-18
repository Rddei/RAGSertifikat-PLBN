import io
import logging

from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger("compliance.fraud")

# pyzbar butuh pustaka sistem (libzbar0). Impor opsional agar aplikasi tetap
# berjalan meski zbar belum terpasang (mis. di sebagian environment dev).
try:
    from pyzbar.pyzbar import decode as decode_qr
    _QR_AVAILABLE = True
except Exception:  # pragma: no cover
    _QR_AVAILABLE = False
    logger.warning("pyzbar/zbar tidak tersedia - pemindaian QR dilewati")

EDITOR_KEYWORDS = (
    "adobe", "photoshop", "canva", "gimp", "lightroom",
    "pixlr", "snapseed", "picsart", "coreldraw", "affinity",
)


def _scan_exif(img: Image.Image) -> list[str]:
    flags: list[str] = []
    try:
        exif = img.getexif()
    except Exception as e:
        logger.warning("Gagal membaca EXIF: %s", e)
        return flags
    if not exif:
        return flags
    for tag_id, value in exif.items():
        tag_name = TAGS.get(tag_id, tag_id)
        if tag_name in ("Software", "ProcessingSoftware"):
            val_lower = str(value).lower()
            if any(kw in val_lower for kw in EDITOR_KEYWORDS):
                flags.append(f"Terindikasi editan software: {value}")
    return flags


def _scan_qr(img: Image.Image) -> list[str]:
    if not _QR_AVAILABLE:
        return []
    data: list[str] = []
    try:
        for obj in decode_qr(img):
            data.append(obj.data.decode("utf-8", errors="replace"))
    except Exception as e:
        logger.warning("Gagal memindai QR: %s", e)
    return data


def scan_for_fraud(image_bytes: bytes) -> tuple[list[str], list[str]]:
    """Kembalikan (fraud_flags, qr_data). Aman terhadap file rusak/non-gambar."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as e:
        logger.warning("Tidak bisa membuka gambar untuk fraud scan: %s", e)
        return [], []
    return _scan_exif(img), _scan_qr(img)
