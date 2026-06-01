// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface VerificationResult {
  metadata: { filename: string; target_major: string };
  security: { fraud_flags: string[]; qr_data: string[] };
  extraction: {
    nama_peserta: string;
    jenjang_sekolah: string;
    nama_lomba: string;
    nama_penyelenggara: string;
  };
  audit: {
    status: string;
    skor_kepatuhan: number;
    langkah_gagal: string | null;
    reasoning: string;
  };
  applicant_id: number;
}

export async function verifyDocument(
  file: File,
  expectedName: string,
  jurusanTujuan: string
): Promise<VerificationResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("expected_name", expectedName);
  formData.append("jurusan_tujuan", jurusanTujuan);

  const response = await fetch(`${API_BASE}/process-document`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Gagal memproses dokumen");
  }

  return response.json();
}