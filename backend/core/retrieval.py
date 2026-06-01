from repositories.chromadb_repo import get_query_engine

async def retrieve_rules(extracted: dict, target_major: str) -> str:
    query_engine = get_query_engine()
    query = (
        f"Aturan admisi untuk jenjang {extracted.get('jenjang_sekolah', '')} "
        f"dan lomba {extracted.get('nama_lomba', '')} "
        f"untuk jurusan {target_major}"
    )
    result = await query_engine.aquery(query)
    return result.response