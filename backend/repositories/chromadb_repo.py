# repositories/chromadb_repo.py
import logging

import chromadb
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.vector_stores.chroma import ChromaVectorStore

from config import GOOGLE_API_KEY, CHROMA_DB_PATH

logger = logging.getLogger("compliance.chromadb")

_index: VectorStoreIndex | None = None
_llm: GoogleGenAI | None = None


def _get_llm() -> GoogleGenAI:
    """LLM Gemini untuk sintesis jawaban RAG (dibangun sekali)."""
    global _llm
    if _llm is None:
        _llm = GoogleGenAI(
            model="models/gemini-2.5-flash",
            api_key=GOOGLE_API_KEY,
        )
    return _llm


def _build_index() -> VectorStoreIndex:
    """Inisialisasi embedding + LLM + koneksi ChromaDB. Dibangun sekali (lazy).

    Lazy init mencegah efek samping berat saat import (mis. saat menjalankan
    test atau saat startup) dan membuat kegagalan koneksi lebih mudah ditangani.
    """
    # PENTING: set embed_model DAN llm ke Gemini secara global. Tanpa Settings.llm,
    # LlamaIndex akan memakai LLM default-nya (OpenAI) saat menyusun jawaban RAG,
    # sehingga muncul error 401 "Incorrect API key" dari api.openai.com.
    Settings.embed_model = GoogleGenAIEmbedding(
        model="models/embedding-001",
        api_key=GOOGLE_API_KEY,
    )
    Settings.llm = _get_llm()

    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_or_create_collection("polban_rules")
    vector_store = ChromaVectorStore(chroma_collection=collection)
    logger.info("ChromaDB index siap (collection: polban_rules)")
    return VectorStoreIndex.from_vector_store(vector_store)


def get_query_engine():
    """Kembalikan query engine; index dibangun saat pertama kali dibutuhkan.

    LLM Gemini diteruskan secara eksplisit ke query engine agar sintesis jawaban
    tidak pernah jatuh ke LLM default (OpenAI), bahkan jika Settings global berubah.
    """
    global _index
    if _index is None:
        _index = _build_index()
    return _index.as_query_engine(llm=_get_llm())
