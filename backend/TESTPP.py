import asyncio
from services.puspresnas import check_kurasi

result = asyncio.run(check_kurasi(
    "PT. KOMPETISI NASIONAL PRESTASI NUSANTARA",
    "Olimpiade Akademik Prestasi Siswa Nusantara 1",
))
print(result)