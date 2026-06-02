from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from models.database import async_engine, Base, AsyncSessionLocal, Admin
from sqlalchemy.future import select
from api.routes import documents, applicants, auth, batch

import logging
logging.getLogger("llama_index").setLevel(logging.ERROR)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).limit(1))
        if not result.scalar_one_or_none():
            session.add(Admin(username="admin", password="polban123"))
            await session.commit()
    yield

app = FastAPI(title="POLBAN Intelligent Compliance Engine", lifespan=lifespan)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(applicants.router)
app.include_router(auth.router)
app.include_router(batch.router)

@app.get("/")
def health_check():
    return {"status": "active", "engine": "Agentic-RAG Full Pipeline"}