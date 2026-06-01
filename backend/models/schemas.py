# models/schemas.py
from pydantic import BaseModel, Field, field_validator

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=200)

class ProcessDocumentForm(BaseModel):
    expected_name: str = Field(..., min_length=2, max_length=200)
    jurusan_tujuan: str = Field(..., min_length=2, max_length=100)

class OverrideStatusForm(BaseModel):
    status: str = Field(..., min_length=1, max_length=50)

class BatchRequestForm(BaseModel):
    expected_names: list[str] = Field(...)
    jurusan_tujuan: str = Field(..., min_length=2, max_length=100)

# Response schema bisa dibuat jika perlu