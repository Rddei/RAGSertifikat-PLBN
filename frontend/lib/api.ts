import { clearToken, getToken } from "./token";
import type {
  Applicant,
  BatchStartResponse,
  BatchStatus,
  LoginResponse,
  Metrics,
  VerifyResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, "Tidak dapat terhubung ke server. Pastikan backend berjalan.");
  }

  // Token tidak valid / kedaluwarsa -> bersihkan & arahkan ke login
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Sesi berakhir. Silakan login kembali.");
  }

  if (!res.ok) {
    let detail = `Terjadi kesalahan (${res.status})`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // body bukan JSON; abaikan
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  async login(username: string, password: string): Promise<LoginResponse> {
    return request<LoginResponse>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  },

  async verifyDocument(
    file: File,
    expectedName: string,
    jurusan: string,
  ): Promise<VerifyResponse> {
    const form = new FormData();
    form.append("file", file);
    form.append("expected_name", expectedName);
    form.append("jurusan_tujuan", jurusan);
    return request<VerifyResponse>("/process-document", {
      method: "POST",
      body: form,
    });
  },

  async getApplicants(): Promise<Applicant[]> {
    const data = await request<{ data: Applicant[] }>("/api/applicants");
    return data.data;
  },

  async getMetrics(): Promise<Metrics> {
    return request<Metrics>("/api/applicants/metrics");
  },

  async overrideStatus(id: number, status: string): Promise<void> {
    const form = new FormData();
    form.append("status", status);
    await request(`/api/applicants/${id}/override`, {
      method: "POST",
      body: form,
    });
  },

  async startBatch(
    files: File[],
    expectedNames: string[],
    jurusan: string,
  ): Promise<BatchStartResponse> {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    expectedNames.forEach((n) => form.append("expected_names", n));
    form.append("jurusan_tujuan", jurusan);
    return request<BatchStartResponse>("/api/audit/batch", {
      method: "POST",
      body: form,
    });
  },

  async getBatchStatus(batchId: number): Promise<BatchStatus> {
    return request<BatchStatus>(`/api/audit/batch/${batchId}`);
  },

  // Unduh CSV: butuh header Authorization, jadi pakai fetch + blob, bukan <a href>.
  async downloadExport(): Promise<void> {
    const token = getToken();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${API_URL}/api/applicants/export`, { headers });
    if (!res.ok) throw new ApiError(res.status, "Gagal mengunduh CSV.");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "laporan_pendaftar.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  async health(): Promise<{ status: string }> {
    return request<{ status: string }>("/health");
  },
};
