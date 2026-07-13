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

  return (
    <div className="min-h-screen">
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
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Daftar Pendaftar</h2>
                <Button variant="ghost" onClick={load}>
                  Muat ulang
                </Button>
              </div>
              <ApplicantsTable applicants={applicants} onChanged={load} />
            </Card>
          </>
        )}
      </main>
    </div>
  );
}