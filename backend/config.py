import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise EnvironmentError("GOOGLE_API_KEY must be set in .env")

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./compliance.db")