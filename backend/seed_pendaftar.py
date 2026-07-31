"""
Seed master pendaftar langsung ke database (tanpa endpoint/Swagger).

Cara pakai (dari folder backend, env aktif, .env terbaca):
    python seed_pendaftar.py

Sifatnya UPSERT berdasarkan id_pendaftaran: aman dijalankan berulang --
baris yang sudah ada diperbarui, tidak diduplikasi. Data di bawah berasal
dari rekap 31 file sertifikat (14 pendaftar unik); jurusan hasil forward-fill
merged cell -- verifikasi manual tetap disarankan.
"""

import asyncio

from sqlalchemy import select

from models.database import AsyncSessionLocal, Pendaftar, Base, async_engine

DATA = [
    ("426161036", "Chelsy Aulia Putri",         "D3 Administrasi Bisnis"),
    ("426570999", "Keisya Kharunissa Afrilian", "D3 Administrasi Bisnis"),
    ("426661534", "Nasya Anindya",              "D3 Bahasa Inggris"),
    ("426636792", "Keyza Muhammad Digdaya",     "D3 Bahasa Inggris"),
    ("426281419", "Jauza Hasri Awalia",         "D3 Bahasa Inggris"),
    ("426759813", "Lascri Amelia Putri",        "D3 Konstruksi Sipil"),
    ("426543159", "Dwi Satrio Wibowo",          "D3 Teknik Aeronautika"),
    ("426446927", "Novel Maha Putri Agustina",  "D3 Teknik Aeronautika"),
    ("426074088", "Rizky Aditya Nugraha",       "D3 Teknik Elektronika"),
    ("426031398", "Fauzan Zhafran Rajiono",     "D3 Teknik Elektronika"),
    ("426031774", "Siti Rayhanun",              "D3 Teknik Kimia"),
    ("426706132", "Dibya Sabda Kencana",        "D3 Teknik Konversi Energi"),
    # Ejaan mayoritas dipakai (2x "Putera" vs 1x "Putra") -- cek bila sempat.
    ("426662402", "Rakha Putera Pratama",       "D3 Teknik Konversi Energi"),
    ("426242037", "Malik Al Hakim",             "D3 Teknik Listrik"),
]


async def main() -> None:
    # Pastikan tabel ada (aman bila sudah ada; tidak menghapus data).
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    dibuat, diperbarui = 0, 0
    async with AsyncSessionLocal() as db:
        for idp, nama, jurusan in DATA:
            res = await db.execute(
                select(Pendaftar).where(Pendaftar.id_pendaftaran == idp)
            )
            row = res.scalar_one_or_none()
            if row:
                row.nama, row.jurusan_dituju = nama, jurusan
                diperbarui += 1
            else:
                db.add(Pendaftar(id_pendaftaran=idp, nama=nama,
                                 jurusan_dituju=jurusan))
                dibuat += 1
        await db.commit()

        total = len((await db.execute(select(Pendaftar))).scalars().all())
    print(f"Seed selesai: {dibuat} baru, {diperbarui} diperbarui, "
          f"total pendaftar di database: {total}")


if __name__ == "__main__":
    asyncio.run(main())
