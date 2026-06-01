import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

from config import GOOGLE_API_KEY, CHROMA_DB_PATH

embed_model = GoogleGenAIEmbedding(model="models/embedding-001", api_key=GOOGLE_API_KEY)
Settings.embed_model = embed_model

_chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
_chroma_collection = _chroma_client.get_or_create_collection("polban_rules")
_vector_store = ChromaVectorStore(chroma_collection=_chroma_collection)
_index = VectorStoreIndex.from_vector_store(_vector_store)

def get_query_engine():
    return _index.as_query_engine()