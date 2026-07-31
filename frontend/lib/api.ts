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

  async startBatch(files: File[]): Promise<BatchStartResponse> {
    // Mode file-only: identitas & jurusan di-lookup backend dari nama file
    // '<id_pendaftar>-<indeks>.<ext>' terhadap master pendaftar.
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<BatchStartResponse>("/api/audit/batch", {
      method: "POST",
      body: form,
    });
  },

  async getBatchStatus(batchId: number): Promise<BatchStatus> {
    return request<BatchStatus>(`/api/audit/batch/${batchId}`);
  },

  // Unduh laporan (CSV/XLSX): butuh header Authorization, jadi pakai fetch + blob.
  async downloadExport(format: "csv" | "xlsx" = "csv"): Promise<void> {
    const token = getToken();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${API_URL}/api/applicants/export?format=${format}`, {
      headers,
    });
    if (!res.ok) throw new ApiError(res.status, "Gagal mengunduh laporan.");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `laporan_pendaftar.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  async health(): Promise<{ status: string }> {
    return request<{ status: string }>("/health");
  },

  // ==========================================
  // FITUR KNOWLEDGE BASE (KB) UNTUK ADMIN
  // ==========================================
  
  async getKbContent(): Promise<{ status: string; content: string }> {
    return request<{ status: string; content: string }>("/api/kb/content");
  },

  async updateKbContent(content: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>("/api/kb/content", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
  },

  async syncKb(): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>("/api/kb/ingest", {
      method: "POST",
    });
  },
};

export function certificateFileUrl(id: number): string {
  return `${API_URL}/api/applicants/${id}/file`;
}

/** Ambil berkas sertifikat (ber-token) lalu buka di tab baru. */
export async function openCertificateFile(id: number): Promise<void> {
  const token = getToken();
  const res = await fetch(certificateFileUrl(id), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new ApiError(res.status, "Berkas sertifikat tidak tersedia di server.");
  }
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
