from core.genai_utils import call_with_retry
from config import RAG_SYNTHESIS
from repositories.chromadb_repo import get_query_engine, get_retriever


async def retrieve_rules(extracted: dict, target_major: str) -> str:
    """Ambil aturan prestasi yang diakui untuk PROGRAM STUDI TUJUAN.

    Query difokuskan ke daftar prestasi yang diakui prodi tujuan (bukan sekadar
    ke nama lomba) agar model bisa menilai relevansi secara berbasis-daftar:
    apakah jenis lomba pada sertifikat termasuk yang diakui prodi tersebut.
    """
    nama_lomba = extracted.get("nama_lomba", "")
    singkatan = extracted.get("singkatan_lomba", "")
    kategori = extracted.get("kategori", "")
    tingkat = extracted.get("tingkat", "")
    query = (
        f"Daftar lengkap prestasi/lomba yang DIAKUI dan bobot komponen prestasi "
        f"untuk program studi '{target_major}' pada SNBP POLBAN. Sebutkan seluruh "
        f"jenis lomba yang diakui per tingkat (Internasional, Nasional, "
        f"Kabupaten/Kota, Lokal). Perlakukan tingkat 'Provinsi' sebagai setara "
        f"dengan tingkat 'Kabupaten/Kota'. "
        f"Tentukan pula apakah lomba '{nama_lomba}' (singkatan '{singkatan}', "
        f"kategori '{kategori}', tingkat '{tingkat}') termasuk prestasi yang "
        f"diakui untuk program studi '{target_major}'."
    )
    if not RAG_SYNTHESIS:
        # Jalur hemat kuota: ambil potongan pedoman langsung dari indeks
        # vektor. Tidak ada panggilan LLM di tahap ini; konteks mentah
        # diserahkan apa adanya kepada auditor.
        nodes = await get_retriever().aretrieve(query)
        potongan = [n.get_content().strip() for n in nodes if n.get_content().strip()]
        if not potongan:
            return "Tidak ada potongan pedoman relevan yang ditemukan pada basis pengetahuan."
        return "\n\n---\n\n".join(potongan)

    query_engine = get_query_engine()
    result = await call_with_retry(
        lambda: query_engine.aquery(query),
        what="Retrieval aturan (RAG/Gemini)",
    )
    return result.response
