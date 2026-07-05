// Tipe yang mencerminkan kontrak respons backend FastAPI.

export interface AuditResult {
  status: string;
  skor_kepatuhan: number;
  langkah_gagal: string | null;
  reasoning: string;
}

// Flag SIMT PUSPRESNAS - informatif, TIDAK memengaruhi skor kepatuhan.
export interface SimtFlags {
  penyelenggara_checked?: boolean | null;
  penyelenggara_terkurasi?: boolean | null;
  nama_terdaftar_simt?: boolean | null;
  nama_cocok_simt?: boolean | null;
  portofolio_checked?: boolean | null;
  tingkat_keyakinan_simt?: string | null;
  ambigu_nama_simt?: boolean | null;
}

export interface VerifyResponse {
  metadata: { filename: string; target_major: string };
  security: { fraud_flags: string[]; qr_data: string[] };
  extraction: Record<string, unknown>;
  audit: AuditResult;
  legalitas?: Record<string, unknown> | null;
  keaslian_sertifikat?: Record<string, unknown> | null;
  flags?: SimtFlags;
  applicant_id: number;
}

export interface Applicant {
  id: number;
  batch_id: number | null;
  filename: string;
  applicant_name: string | null;
  target_major: string | null;
  skor_kepatuhan: number | null;
  ai_status: string | null;
  final_status: string | null;
  fraud_flags: string[];
  qr_data: string[];
  reasoning: string | null;
  // Flag SIMT PUSPRESNAS (informatif, bukan bagian skor)
  nisn: string | null;
  asal_sekolah: string | null;
  nama_terdaftar_simt: boolean | null;
  tingkat_keyakinan_simt: string | null;
  penyelenggara_terkurasi: boolean | null;
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
