"""Utilitas ketahanan (resilience) untuk panggilan model AI Gemini.

Modul ini menyediakan retry otomatis dengan exponential backoff untuk
error sementara (transient) seperti 503 UNAVAILABLE ("high demand"),
429 (rate limit), dan 5xx lain. Tujuannya agar lonjakan beban di sisi
Google tidak langsung menggagalkan seluruh permintaan pengguna.
"""
import asyncio
import logging

logger = logging.getLogger("compliance.genai")

# Kode status HTTP yang dianggap sementara sehingga layak dicoba ulang.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ModelUnavailableError(Exception):
    """Dilempar ketika model AI tetap tidak tersedia setelah beberapa percobaan."""


def _status_code_of(exc: Exception):
    """Ambil kode status HTTP dari berbagai bentuk exception google-genai / llama-index."""
    for attr in ("code", "status_code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    # Beberapa error menyimpan kode di dalam atribut .response.
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    if isinstance(code, int):
        return code
    # Fallback terakhir: cari kode status umum di dalam pesan error.
    msg = str(exc)
    for code in (503, 429, 500, 502, 504):
        if str(code) in msg:
            return code
    return None


async def call_with_retry(
    coro_factory,
    *,
    what: str = "panggilan model AI",
    max_attempts: int = 4,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
):
    """Jalankan coroutine dengan retry + exponential backoff untuk error sementara.

    Args:
        coro_factory: fungsi TANPA argumen yang MENGEMBALIKAN coroutine baru tiap
            dipanggil. Penting: satu coroutine tidak bisa di-await dua kali,
            jadi gunakan lambda, mis. ``lambda: client.aio.models.generate_content(...)``.
        what: deskripsi singkat untuk log.
        max_attempts: jumlah maksimum percobaan.
        base_delay: jeda awal (detik), digandakan tiap percobaan (2s, 4s, 8s, ...).
        max_delay: batas atas jeda (detik).

    Returns:
        Hasil dari coroutine bila berhasil.

    Raises:
        ModelUnavailableError: bila semua percobaan gagal karena error sementara.
        Exception: error non-transient diteruskan apa adanya.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_factory()
        except Exception as exc:  # noqa: BLE001 - difilter via kode status
            status = _status_code_of(exc)
            is_retryable = status in RETRYABLE_STATUS_CODES

            # Error permanen (mis. 400/401/403/404) langsung diteruskan.
            if not is_retryable:
                raise

            last_exc = exc
            if attempt >= max_attempts:
                logger.error(
                    "%s gagal setelah %d percobaan (status=%s).",
                    what, attempt, status,
                )
                raise ModelUnavailableError(
                    "Model AI sedang sibuk atau tidak tersedia. "
                    "Silakan coba lagi beberapa saat lagi."
                ) from exc

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "%s gagal (status=%s), percobaan %d/%d. Menunggu %.1fs lalu coba lagi...",
                what, status, attempt, max_attempts, delay,
            )
            await asyncio.sleep(delay)

    # Jaring pengaman (secara teori tidak tercapai).
    raise ModelUnavailableError(
        "Model AI sedang sibuk atau tidak tersedia. Silakan coba lagi beberapa saat lagi."
    ) from last_exc
