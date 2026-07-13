// Tipe yang mencerminkan kontrak respons backend FastAPI.

export interface AuditResult {
  status: string;
  skor_kepatuhan: number;
  langkah_gagal: string | null;
  reasoning: string;
}

export interface KurasiResult {
  checked: boolean;
  status: string;
  terkurasi: boolean | null;
  skor_nama: number;
  skor_penyelenggara: number;
  ajang_terdekat: string | null;
  penyelenggara_terdekat: string | null;
  level_terdekat: string | null;
  kategori_terdekat: string | null;
  sumber?: string;
  error?: string | null;
}

export interface VerifyResponse {
  metadata: { filename: string; target_major: string };
  security: { fraud_flags: string[]; qr_data: string[] };
  extraction: Record<string, unknown>;
  audit: AuditResult;
  kurasi?: KurasiResult;
  applicant_id: number;
}

export interface Applicant {
  id: number;
  batch_id: number | null;
  filename: string;
  applicant_name: string | null;
  target_major: string | null;

  // --- Hasil ekstraksi sertifikat (Gemini Vision) ---
  nama_peserta: string | null;
  nama_lomba: string | null;
  singkatan_lomba: string | null;
  nama_penyelenggara: string | null;
  kategori: string | null;
  tingkat: string | null;
  tanggal_kegiatan: string | null;
  peringkat: string | null;
  nomor_sertifikat: string | null;
  url_verifikasi: string | null;
  penandatangan: string | null;
  ada_cap: boolean | null;
  deskripsi_cap: string | null;
  ada_ttd: boolean | null;

  skor_kepatuhan: number | null;
  ai_status: string | null;
  final_status: string | null;

  // --- Kurasi SIMT ---
  kurasi_status: string | null;
  kurasi_skor_nama: number | null;
  kurasi_skor_penyelenggara: number | null;
  kurasi_ajang_terdekat: string | null;

  fraud_flags: string[];
  qr_data: string[];
  reasoning: string | null;
  created_at: string | null;
}

export interface Metrics {
  total: number;
  diterima: number;
  ditolak: number;
  fraud: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface BatchStartResponse {
  message: string;
  batch_id: number;
  total_files: number;
}

export interface BatchStatus {
  batch_id: number;
  total: number;
  processed: number;
  status: string;
  applicants_processed: number;
}

// Harus sama dengan StatusLiteral di backend (models/schemas.py)
export const STATUS_OPTIONS = ["Diterima", "Ditolak", "Butuh Tinjauan Manual"] as const;
export type StatusOption = (typeof STATUS_OPTIONS)[number];
