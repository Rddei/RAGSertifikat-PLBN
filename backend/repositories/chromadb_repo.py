# repositories/chromadb_repo.py
import logging

import chromadb
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from config import GOOGLE_API_KEY, CHROMA_DB_PATH

logger = logging.getLogger("compliance.chromadb")

_index: VectorStoreIndex | None = None


def _build_index() -> VectorStoreIndex:
    """Inisialisasi embedding + koneksi ChromaDB. Dibangun sekali (lazy).

    Lazy init mencegah efek samping berat saat import (mis. saat menjalankan
    test atau saat startup) dan membuat kegagalan koneksi lebih mudah ditangani.
    """
    Settings.embed_model = GoogleGenAIEmbedding(
        model="models/embedding-001",
        api_key=GOOGLE_API_KEY,
    )
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_or_create_collection("polban_rules")
    vector_store = ChromaVectorStore(chroma_collection=collection)
    logger.info("ChromaDB index siap (collection: polban_rules)")
    return VectorStoreIndex.from_vector_store(vector_store)


def get_query_engine():
    """Kembalikan query engine; index dibangun saat pertama kali dibutuhkan."""
    global _index
    if _index is None:
        _index = _build_index()
    return _index.as_query_engine()
