"""Utilitas ketahanan (resilience) untuk panggilan model AI Gemini.

Modul ini menyediakan retry otomatis dengan exponential backoff untuk
error sementara (transient) seperti 503 UNAVAILABLE ("high demand"),
429 (rate limit), dan 5xx lain. Tujuannya agar lonjakan beban di sisi
Google tidak langsung menggagalkan seluruh permintaan pengguna.
"""
import asyncio
import logging
import random
import re

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


def _retry_delay_of(exc: Exception) -> float:
    """Ambil saran jeda (detik) dari error 429 Gemini (RetryInfo), bila ada.

    Google mengirim saran jeda pada balasan 429, mis. `"retryDelay": "34s"`
    atau `retry_delay { seconds: 34 }`. Menghormatinya jauh lebih efektif
    daripada backoff buta saat yang terjadi adalah limit per-menit (RPM).
    """
    msg = str(exc)
    m = re.search(r"retry.?delay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"seconds['\"]?\s*[:=]\s*(\d+)", msg, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 0.0


async def call_with_retry(
    coro_factory,
    *,
    what: str = "panggilan model AI",
    max_attempts: int = 6,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
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

            backoff = min(base_delay * (2 ** (attempt - 1)), max_delay)
            server_delay = _retry_delay_of(exc)
            # Hormati saran server (RetryInfo) bila ada; jika tidak, pakai backoff.
            delay = min(max(backoff, server_delay), max_delay) + random.uniform(0, 0.75)
            logger.warning(
                "%s gagal (status=%s), percobaan %d/%d. Menunggu %.1fs lalu coba lagi...%s",
                what, status, attempt, max_attempts, delay,
                f" (server menyarankan {server_delay:.0f}s)" if server_delay else "",
            )
            await asyncio.sleep(delay)

    # Jaring pengaman (secara teori tidak tercapai).
    raise ModelUnavailableError(
        "Model AI sedang sibuk atau tidak tersedia. Silakan coba lagi beberapa saat lagi."
    ) from last_exc
