import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.future import select

from config import (
    CORS_ORIGINS, IS_PRODUCTION, ADMIN_USERNAME, ADMIN_PASSWORD,
)
from models.database import async_engine, AsyncSessionLocal, Base, Admin
from security import hash_password
from api.routes import auth, documents, batch, applicants

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("compliance.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Buat tabel jika belum ada
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed admin default dengan password TER-HASH (aman)
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Admin).where(Admin.username == ADMIN_USERNAME)
        )
        if existing.scalar_one_or_none() is None:
            db.add(Admin(username=ADMIN_USERNAME, password=hash_password(ADMIN_PASSWORD)))
            await db.commit()
            logger.info("Admin default dibuat (username=%s)", ADMIN_USERNAME)
    yield
    await async_engine.dispose()


app = FastAPI(
    title="POLBAN Intelligent Compliance Engine",
    lifespan=lifespan,
    # Sembunyikan dokumentasi interaktif di produksi
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,        # spesifik, bukan "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(batch.router)
app.include_router(applicants.router)


@app.get("/health")
async def health():
    """Health check: pastikan API + koneksi DB sehat."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception as e:
        logger.exception("Health check gagal")
        return {"status": "degraded", "database": "error", "detail": str(e)}


@app.get("/")
async def root():
    return {"status": "ok", "service": app.title}
