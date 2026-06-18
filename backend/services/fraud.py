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

# PyMuPDF dipakai untuk merender halaman pertama PDF menjadi gambar agar
# EXIF/QR tetap bisa dipindai. Opsional: jika tidak terpasang, fraud scan
# untuk berkas PDF akan dilewati dengan aman (tanpa menggagalkan pipeline).
try:
    import fitz  # PyMuPDF
    _PDF_AVAILABLE = True
except Exception:  # pragma: no cover
    _PDF_AVAILABLE = False
    logger.info("PyMuPDF (fitz) tidak tersedia - fraud scan untuk PDF dilewati")

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


def _is_pdf(image_bytes: bytes, content_type: str | None) -> bool:
    if content_type == "application/pdf":
        return True
    return image_bytes[:5] == b"%PDF-"


def _load_image(image_bytes: bytes, content_type: str | None) -> Image.Image | None:
    """Muat berkas menjadi objek gambar PIL.

    Untuk PDF, halaman pertama dirender menjadi gambar (butuh PyMuPDF).
    Mengembalikan None bila berkas PDF tetapi PyMuPDF tidak tersedia.
    """
    if _is_pdf(image_bytes, content_type):
        if not _PDF_AVAILABLE:
            logger.info("Berkas PDF & PyMuPDF tidak terpasang - fraud scan dilewati.")
            return None
        doc = fitz.open(stream=image_bytes, filetype="pdf")
        try:
            if doc.page_count == 0:
                return None
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=150)
            return Image.open(io.BytesIO(pix.tobytes("png")))
        finally:
            doc.close()
    return Image.open(io.BytesIO(image_bytes))


def scan_for_fraud(
    image_bytes: bytes, content_type: str | None = None
) -> tuple[list[str], list[str]]:
    """Kembalikan (fraud_flags, qr_data). Aman terhadap berkas rusak/non-gambar/PDF."""
    try:
        img = _load_image(image_bytes, content_type)
        if img is None:
            return [], []
        img.load()
    except Exception as e:
        logger.warning("Tidak bisa membuka berkas untuk fraud scan: %s", e)
        return [], []
    return _scan_exif(img), _scan_qr(img)
