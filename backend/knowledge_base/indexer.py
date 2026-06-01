# knowledge_base/indexer.py
import os
import chromadb
from llama_index.core import SimpleDirectoryReader, Settings, VectorStoreIndex, StorageContext
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.node_parser import SentenceSplitter
from config import GOOGLE_API_KEY, CHROMA_DB_PATH

# Inisialisasi embedding model
embed_model = GoogleGenAIEmbedding(model="models/embedding-001", api_key=GOOGLE_API_KEY)
Settings.embed_model = embed_model

# Tentukan direktori sumber dokumen (folder data/)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def build_knowledge_base():
    if not os.path.exists(DATA_DIR) or not os.listdir(DATA_DIR):
        raise FileNotFoundError(f"Tidak ada file di {DATA_DIR}. Letakkan file PDF pedoman di sini.")

    # Baca dokumen
    reader = SimpleDirectoryReader(DATA_DIR)
    documents = reader.load_data()
    print(f"Berhasil memuat {len(documents)} dokumen.")

    # Potong menjadi chunks
    splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=200)
    nodes = splitter.get_nodes_from_documents(documents)
    print(f"Terbentuk {len(nodes)} chunks.")

    # Hubungkan ke ChromaDB
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    chroma_collection = chroma_client.get_or_create_collection("polban_rules")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Buat dan simpan indeks
    index = VectorStoreIndex(nodes, storage_context=storage_context)
    print("Knowledge base berhasil diindeks ke ChromaDB.")

if __name__ == "__main__":
    build_knowledge_base()