import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.future import select

from config import (
    CORS_ORIGINS, IS_PRODUCTION, ADMIN_USERNAME, ADMIN_PASSWORD,
)
from models.database import async_engine, AsyncSessionLocal, Base, User
from security import hash_password
from api.routes import auth, documents, batch, applicants, knowledge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("compliance.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Buat tabel jika belum ada di PostgreSQL
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed admin dan verifikator default
    async with AsyncSessionLocal() as db:
        # 1. SEED ADMIN
        existing_admin = await db.execute(
            select(User).where(User.username == ADMIN_USERNAME)
        )
        if existing_admin.scalar_one_or_none() is None:
            db.add(User(
                username=ADMIN_USERNAME, 
                password=hash_password(ADMIN_PASSWORD),
                role="admin"
            ))
            logger.info("Admin default dibuat (username=%s, role=admin)", ADMIN_USERNAME)

        # 2. SEED VERIFIKATOR DEFAULT (Untuk Testing & MVP)
        # Anda bisa mengubah username dan password ini sesuai keinginan
        verif_username = "verifikator1"
        verif_password = "password123"
        
        existing_verif = await db.execute(
            select(User).where(User.username == verif_username)
        )
        if existing_verif.scalar_one_or_none() is None:
            db.add(User(
                username=verif_username,
                password=hash_password(verif_password),
                role="verifikator"
            ))
            logger.info("Verifikator default dibuat (username=%s, role=verifikator)", verif_username)

        # Simpan keduanya ke database
        await db.commit()
        
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
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrasi semua router
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(batch.router)
app.include_router(applicants.router)
app.include_router(knowledge.router) # Router fitur Knowledge Base

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