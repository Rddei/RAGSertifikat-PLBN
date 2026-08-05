"use client";

import { useCallback, useEffect, useState } from "react";
// Jika Anda menggunakan next/link atau next/router untuk navigasi admin
import { useRouter } from "next/navigation"; 
import { Navbar } from "@/components/Navbar";
import { MetricsCards } from "@/components/MetricsCards";
import { ApplicantsTable } from "@/components/ApplicantsTable";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { Applicant, Metrics } from "@/lib/types";

export default function DashboardPage() {
  const { ready, isAuthenticated, user } = useRequireAuth(); 
  const router = useRouter();
  const toast = useToast();
  
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [filterJurusan, setFilterJurusan] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [page, setPage] = useState(1);
  const PER_PAGE = 10;
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, m] = await Promise.all([api.getApplicants(), api.getMetrics()]);
      setApplicants(a);
      setMetrics(m);
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal memuat data.", "error");
    } finally {
      setLoading(false);
    }
    // PERBAIKAN 1: Kosongkan dependency array agar tidak terjadi infinite loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (ready && isAuthenticated) load();
    // PERBAIKAN 2: Hapus 'load' dari dependency array
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, isAuthenticated]);

  async function handleExport(format: "csv" | "xlsx") {
    setExporting(true);
    try {
      await api.downloadExport(format);
      toast.show(`${format.toUpperCase()} berhasil diunduh.`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal mengunduh laporan.", "error");
    } finally {
      setExporting(false);
    }
  }

  if (!ready || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-indigo-600" />
      </div>
    );
  }

  // Daftar jurusan unik untuk opsi filter (dari data yang ada).
  const jurusanOptions = Array.from(
    new Set(applicants.map((a) => a.target_major).filter(Boolean) as string[])
  ).sort();

  // Terapkan filter jurusan + status pada data sebelum ditampilkan.
  const norm = (v: string | null) => (v ?? "").toLowerCase();
  const filteredApplicants = applicants.filter((a) => {
    const okJurusan = !filterJurusan || a.target_major === filterJurusan;
    const status = a.final_status ?? a.ai_status;
    const okStatus = !filterStatus || norm(status) === norm(filterStatus);
    return okJurusan && okStatus;
  });

  // Pagination: 10 baris per halaman.
  const totalPages = Math.max(1, Math.ceil(filteredApplicants.length / PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const pagedApplicants = filteredApplicants.slice(
    (safePage - 1) * PER_PAGE,
    safePage * PER_PAGE,
  );

  return (
    <div className="min-h-screen pt-12 lg:pl-16">
      <Navbar />
      <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <div className="space-x-3">
             {/* PROTEKSI UI: Tombol KB Editor HANYA untuk Admin */}
             {user?.role === "admin" && (
              <Button variant="outline" onClick={() => router.push("/kb-editor")}>
                Kelola Aturan (KB)
              </Button>
            )}
            
            {/* PROTEKSI UI: Tombol Export HANYA untuk Admin */}
            {user?.role === "admin" && (
              <>
                <Button variant="secondary" loading={exporting} onClick={() => handleExport("csv")}>
                  Export CSV
                </Button>
                <Button variant="secondary" loading={exporting} onClick={() => handleExport("xlsx")}>
                  Export XLSX
                </Button>
              </>
            )}
          </div>
        </div>

        {loading || !metrics ? (
          <div className="flex justify-center py-12">
            <Spinner className="h-8 w-8 text-indigo-600" />
          </div>
        ) : (
          <>
            <MetricsCards metrics={metrics} />
            <Card>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">Daftar Pendaftar</h2>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={filterJurusan}
                    onChange={(e) => { setFilterJurusan(e.target.value); setPage(1); }}
                    className="rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    <option value="">Semua Jurusan</option>
                    {jurusanOptions.map((j) => (
                      <option key={j} value={j}>{j}</option>
                    ))}
                  </select>
                  <select
                    value={filterStatus}
                    onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
                    className="rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    <option value="">Semua Status</option>
                    <option value="Diterima">Diterima</option>
                    <option value="Ditolak">Ditolak</option>
                    <option value="Butuh Tinjauan Manual">Butuh Tinjauan Manual</option>
                  </select>
                  <Button variant="ghost" onClick={load}>Muat ulang</Button>
                </div>
              </div>
              <div className="mb-2 text-sm text-slate-500">
                {filteredApplicants.length === 0
                  ? "Tidak ada pendaftar yang cocok"
                  : `Menampilkan ${(safePage - 1) * PER_PAGE + 1}–${Math.min(safePage * PER_PAGE, filteredApplicants.length)} dari ${filteredApplicants.length} pendaftar`}
              </div>
              <ApplicantsTable applicants={pagedApplicants} onChanged={load} />
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={safePage === 1}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                  >
                    ← Sebelumnya
                  </button>
                  <span className="text-sm text-slate-500">
                    Halaman {safePage} dari {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={safePage === totalPages}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                  >
                    Selanjutnya →
                  </button>
                </div>
              )}
            </Card>
          </>
        )}
      </main>
    </div>
  );
}