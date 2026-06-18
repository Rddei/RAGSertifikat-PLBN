from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=200)


class ProcessDocumentForm(BaseModel):
    expected_name: str = Field(..., min_length=2, max_length=200)
    jurusan_tujuan: str = Field(..., min_length=2, max_length=100)

    @field_validator("expected_name", "jurusan_tujuan")
    @classmethod
    def _strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tidak boleh kosong atau hanya spasi")
        return v


# Status final yang valid -> cegah nilai sembarangan masuk DB.
# Sesuaikan daftar ini dengan status yang benar-benar dipakai sistem Anda.
StatusLiteral = Literal["Diterima", "Ditolak", "Butuh Tinjauan Manual"]


class OverrideStatusForm(BaseModel):
    status: StatusLiteral


class BatchRequestForm(BaseModel):
    expected_names: list[str] = Field(..., min_length=1)
    jurusan_tujuan: str = Field(..., min_length=2, max_length=100)

    @field_validator("expected_names")
    @classmethod
    def _no_empty_names(cls, v: list[str]) -> list[str]:
        cleaned = [n.strip() for n in v if n and n.strip()]
        if not cleaned:
            raise ValueError("Daftar nama tidak boleh kosong")
        return cleaned
