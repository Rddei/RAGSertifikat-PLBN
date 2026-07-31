import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Applicant
from core.vision import extract_certificate_data
from core.retrieval import retrieve_rules
from core.audit import run_audit
from services.fraud import scan_for_fraud
from services.kurasi_lokal import check_kurasi_lokal
from services.kriteria_lokal import check_relevansi
from services.rubrik_prestasi import hitung_skor_prestasi

logger = logging.getLogger("compliance.agent")

# Taksonomi "tolak langsung" keluarga-1: jenis dokumen di luar sertifikat
# prestasi perlombaan. Nilai peta = sebab yang ditulis apa adanya pada reasoning.
JENIS_TOLAK_OTOMATIS = {
    "partisipasi": "sertifikat hanya menyatakan keikutsertaan tanpa pencapaian peringkat",
    "kursus_pelatihan": "sertifikat penyelesaian kursus/pelatihan, bukan prestasi perlombaan",
    "penghargaan_non_lomba": "penghargaan non-perlombaan (mis. siswa terbaik/teladan)",
    "bukan_sertifikat": "dokumen tidak teridentifikasi sebagai sertifikat",
}


async def _persist_non_certificate(db, filename, expected_name, target_major,
                                   batch_id, verifikator_id, id_pendaftaran,
                                   extracted, fraud_flags, qr_data,
                                   reasoning: str | None = None) -> dict:
    """Simpan berkas di luar kategori sertifikat prestasi sebagai Ditolak.

    Zona tolak otomatis: tahapan AI lanjutan (RAG, kurasi, kriteria, audit)
    TIDAK dijalankan dan poin prestasi TIDAK dihitung (skor_prestasi=None ->
    ditampilkan "-" pada antarmuka).
    """
    if not reasoning:
        reasoning = ("**Kesimpulan:** DITOLAK OTOMATIS - Bukan Sertifikat Prestasi: "
                     "dokumen tidak teridentifikasi sebagai sertifikat prestasi "
                     "(nama peserta, nama lomba, dan peringkat tidak ditemukan). "
                     "Poin prestasi tidak dihitung.")
    applicant = Applicant(
        batch_id=batch_id, verifikator_id=verifikator_id, filename=filename,
        applicant_name=expected_name, target_major=target_major,
        id_pendaftaran=id_pendaftaran,
        nama_peserta=extracted.get("nama_peserta", ""),
        nama_lomba=extracted.get("nama_lomba", ""),
        singkatan_lomba=extracted.get("singkatan_lomba", ""),
        nama_penyelenggara=extracted.get("nama_penyelenggara", ""),
        kategori=extracted.get("kategori", ""),
        tingkat=extracted.get("tingkat", ""),
        tanggal_kegiatan=extracted.get("tanggal_pelaksanaan", ""),
        tanggal_terbit=extracted.get("tanggal_terbit", ""),
        peringkat=extracted.get("peringkat", ""),
        nomor_sertifikat=extracted.get("nomor_sertifikat", ""),
        url_verifikasi=extracted.get("url_verifikasi", ""),
        penandatangan=extracted.get("penandatangan", ""),
        ada_cap=bool(extracted.get("ada_cap", False)),
        deskripsi_cap=extracted.get("deskripsi_cap", ""),
        ada_ttd=bool(extracted.get("ada_ttd", False)),
        kriteria_relevansi=None, skor_prestasi=None,
        fraud_flags=json.dumps(fraud_flags), qr_data=json.dumps(qr_data),
        skor_kepatuhan=0, ai_status="Ditolak", final_status="Ditolak",
        reasoning=reasoning,
        kurasi_status=None, kurasi_skor_nama=None,
        kurasi_skor_penyelenggara=None, kurasi_ajang_terdekat=None,
    )
    try:
        db.add(applicant)
        await db.commit()
        await db.refresh(applicant)
    except Exception:
        await db.rollback()
        raise
    return {"applicant_id": applicant.id, "status": "Ditolak",
            "skor_kepatuhan": 0, "reasoning": reasoning,
            "bukan_sertifikat": True}


async def process_single_application(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    target_major: str,
    expected_name: str,
    db: AsyncSession,
    batch_id: int | None = None,
    verifikator_id: int | None = None,
    id_pendaftaran: str | None = None,
) -> dict:
    logger.info("Memproses %s (jurusan=%s)", filename, target_major)

    # Stage 0: Fraud detection
    fraud_flags, qr_data = scan_for_fraud(image_bytes, content_type)

    # Stage 1: Extraction
    extracted = await extract_certificate_data(image_bytes, content_type)

    # ---- Gerbang jenis sertifikat (zona tolak otomatis) --------------------
    # Hanya sertifikat PRESTASI PERLOMBAAN yang berhak menempuh tahapan AI
    # lanjutan. Kelas ragu ("tidak_dapat_ditentukan") sengaja DILANJUTKAN agar
    # ketidakpastian tetap dieskalasi ke manusia, bukan ditolak mesin (BR-08).
    _jenis = str(extracted.get("jenis_sertifikat", "")).strip().lower()
    if _jenis in JENIS_TOLAK_OTOMATIS:
        logger.warning("Berkas %s ditolak gerbang jenis: %s", filename, _jenis)
        return await _persist_non_certificate(
            db, filename, expected_name, target_major, batch_id,
            verifikator_id, id_pendaftaran, extracted, fraud_flags, qr_data,
            reasoning=(
                "**Kesimpulan:** DITOLAK OTOMATIS - Bukan Sertifikat Prestasi: "
                f"{JENIS_TOLAK_OTOMATIS[_jenis]}. Berkas tidak menempuh tahapan "
                "pemeriksaan kepatuhan lanjutan dan poin prestasi tidak dihitung."
            ),
        )

    # Gerbang dini (jaring pengaman kedua): berkas dengan field-field kunci
    # kosong semua DITOLAK tanpa membayar RAG/kurasi/audit. Deteksi sengaja
    # konservatif: butuh nama peserta DAN nama lomba DAN peringkat kosong.
    _kunci = [extracted.get("nama_peserta", ""), extracted.get("nama_lomba", ""),
              extracted.get("peringkat", "")]
    if not any(str(v).strip() for v in _kunci):
        logger.warning("Berkas %s tidak teridentifikasi sebagai sertifikat", filename)
        return await _persist_non_certificate(
            db, filename, expected_name, target_major, batch_id,
            verifikator_id, id_pendaftaran, extracted, fraud_flags, qr_data)

    # Stage 2: RAG
    rag_context = await retrieve_rules(extracted, target_major)

    # Stage 2.5: Kurasi SIMT (lokal, dari data hasil scraping).
    # Dijalankan di thread terpisah agar pencocokan (~ribuan baris) tidak
    # memblokir event loop. AMAN: fungsi tidak melempar error.
    kurasi = await asyncio.to_thread(
        check_kurasi_lokal,
        extracted.get("nama_lomba", ""),
        extracted.get("singkatan_lomba", ""),
        extracted.get("nama_penyelenggara", ""),
        extracted.get("tingkat", ""),
    )

    # Stage 2.6: Lookup kriteria resmi (deterministik, in-memory -> murah).
    # Hasilnya menjadi FAKTA relevansi bagi auditor; RAG turun peran jadi
    # konteks naratif. Fail-safe: status 'ambigu' bila ada masalah.
    kriteria_resmi = check_relevansi(
        target_major,
        extracted.get("nama_lomba", ""),
        extracted.get("singkatan_lomba", ""),
        extracted.get("kategori", ""),
        extracted.get("tingkat", ""),
    )

    # Stage 2.7: Poin prestasi menurut rubrik resmi (deterministik,
    # INFORMATIF -- terpisah total dari vonis kepatuhan; tidak dikirim
    # ke LLM agar tidak mencemari penilaian kriteria).
    skor_prestasi = hitung_skor_prestasi(
        extracted.get("kategori", ""),
        extracted.get("nama_lomba", ""),
        extracted.get("tingkat", ""),
        extracted.get("peringkat", ""),
    )

    # Stage 3: Audit
    audit = await run_audit(
        extracted, target_major, expected_name, fraud_flags, qr_data, rag_context,
        kurasi=kurasi,
        kriteria_resmi=kriteria_resmi,
    )

    # Stage 4: Persist (dengan rollback bila gagal)
    applicant = Applicant(
        batch_id=batch_id,
        verifikator_id=verifikator_id,
        filename=filename,
        applicant_name=expected_name,
        target_major=target_major,
        id_pendaftaran=id_pendaftaran,
        # --- Hasil ekstraksi sertifikat (Vision) ---
        nama_peserta=extracted.get("nama_peserta", ""),
        nama_lomba=extracted.get("nama_lomba", ""),
        singkatan_lomba=extracted.get("singkatan_lomba", ""),
        nama_penyelenggara=extracted.get("nama_penyelenggara", ""),
        kategori=extracted.get("kategori", ""),
        tingkat=extracted.get("tingkat", ""),
        tanggal_kegiatan=extracted.get("tanggal_pelaksanaan",
                                       extracted.get("tanggal", "")),
        tanggal_terbit=extracted.get("tanggal_terbit", ""),
        peringkat=extracted.get("peringkat", ""),
        nomor_sertifikat=extracted.get("nomor_sertifikat", ""),
        url_verifikasi=extracted.get("url_verifikasi", ""),
        penandatangan=extracted.get("penandatangan", ""),
        ada_cap=bool(extracted.get("ada_cap", False)),
        deskripsi_cap=extracted.get("deskripsi_cap", ""),
        ada_ttd=bool(extracted.get("ada_ttd", False)),
        # --- Keamanan & audit ---
        kriteria_relevansi=json.dumps(kriteria_resmi, ensure_ascii=False),
        skor_prestasi=json.dumps(skor_prestasi, ensure_ascii=False),
        fraud_flags=json.dumps(fraud_flags),
        qr_data=json.dumps(qr_data),
        skor_kepatuhan=audit.get("skor_kepatuhan", 0),
        ai_status=audit.get("status", "Unknown"),
        final_status=audit.get("status", "Unknown"),
        reasoning=audit.get("reasoning", ""),
        # --- Kurasi SIMT (lokal, dari data hasil scraping) ---
        kurasi_status=kurasi.get("status"),
        kurasi_skor_nama=kurasi.get("skor_nama"),
        kurasi_skor_penyelenggara=kurasi.get("skor_penyelenggara"),
        kurasi_ajang_terdekat=kurasi.get("ajang_terdekat"),
    )

    db.add(applicant)
    try:
        await db.commit()
        await db.refresh(applicant)
    except Exception:
        await db.rollback()
        logger.exception("Gagal menyimpan applicant untuk file %s", filename)
        raise

    return {
        "metadata": {"filename": filename, "target_major": target_major},
        "security": {"fraud_flags": fraud_flags, "qr_data": qr_data},
        "extraction": extracted,
        "kurasi": kurasi,
        "kriteria_resmi": kriteria_resmi,
        "skor_prestasi": skor_prestasi,
        "audit": audit,
        "applicant_id": applicant.id,
    }
