from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime

from config import DATABASE_URL

async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

class BatchJob(Base):
    __tablename__ = "batch_jobs"
    id = Column(Integer, primary_key=True)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    status = Column(String, default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)
    applicants = relationship("Applicant", back_populates="batch")

class Applicant(Base):
    __tablename__ = "applicants"
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batch_jobs.id"), nullable=True)
    filename = Column(String, nullable=False)
    applicant_name = Column(String)
    target_major = Column(String)
    fraud_flags = Column(Text)
    qr_data = Column(Text)
    skor_kepatuhan = Column(Float, default=0.0)
    ai_status = Column(String)
    final_status = Column(String)
    reasoning = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    batch = relationship("BatchJob", back_populates="applicants")