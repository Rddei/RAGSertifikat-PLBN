"use client";

import { useState } from "react";
import { useRouter } from "next/navigation"; // TAMBAHKAN useRouter
import { Navbar } from "@/components/Navbar";
import { FileUpload } from "@/components/FileUpload";
// import { ComplianceResult } from "@/components/ComplianceResult"; // Kita nonaktifkan dulu karena kita akan redirect ke dashboard
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";

export default function UploadPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const router = useRouter();
  const toast = useToast();
  
  const [file, setFile] = useState<File | null>(null);
  const [expectedName, setExpectedName] = useState("");
  const [jurusan, setJurusan] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false); // STATE BARU UNTUK POLLING

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      toast.show("Pilih berkas terlebih dahulu.", "error");
      return;
    }
    
    setLoading(true);
    
    try {
      // 1. Tembak API Upload (Sekarang merespons instan dengan status 202)
      await api.verifyDocument(file, expectedName, jurusan);
      
      toast.show("Dokumen diterima! AI sedang menganalisis di latar belakang...", "success");
      setIsPolling(true); // Mulai UI Polling

      // 2. MEKANISME POLLING (Ping server setiap 3 detik)
      let attempts = 0;
      const maxAttempts = 20; // Maksimal 60 detik (20 * 3 dtk) untuk mencegah infinite loop
      let isDone = false;

      while (attempts < maxAttempts && !isDone) {
        attempts++;
        
        // Jeda 3 detik
        await new Promise((resolve) => setTimeout(resolve, 3000));
        
        try {
          // Ambil daftar dokumen terbaru (Asumsi api.getApplicants memanggil GET /api/applicants)
          const res = await api.getApplicants();
          
          // Cari apakah file yang baru saja diunggah sudah selesai diproses dan masuk DB
          const processedDoc = res.data.find(
            (doc: any) => doc.filename === file.name && doc.applicant_name === expectedName
          );

          if (processedDoc) {
            isDone = true;
            toast.show("Verifikasi Selesai! Mengalihkan ke hasil...", "success");
            // Mengarahkan pengguna langsung ke halaman dashboard / detail
            router.push("/dashboard"); 
          }
        } catch (pollErr) {
          console.error("Gagal mengecek status:", pollErr);
        }
      }

      if (!isDone) {
        toast.show("Proses memakan waktu lebih lama dari perkiraan. Silakan cek Dashboard Anda secara berkala.", "error");
        router.push("/dashboard"); 
      }

    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Gagal mengunggah dokumen.", "error");
    } finally {
      setLoading(false);
      setIsPolling(false);
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
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <h1 className="text-2xl font-bold">Verifikasi Sertifikat</h1>
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Nama Pendaftar (sesuai dokumen)
              </label>
              <Input
                value={expectedName}
                onChange={(e) => setExpectedName(e.target.value)}
                placeholder="mis. Budi Santoso"
                required
                disabled={loading || isPolling} // Kunci input saat loading
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Jurusan Tujuan
              </label>
              <Input
                value={jurusan}
                onChange={(e) => setJurusan(e.target.value)}
                placeholder="mis. Teknik Informatika"
                required
                disabled={loading || isPolling}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Berkas Sertifikat
              </label>
              {/* Sembunyikan uploader saat AI sedang bekerja agar UI lebih fokus */}
              <FileUpload file={file} onSelect={setFile} disabled={loading || isPolling} />
            </div>
            
            <Button 
              type="submit" 
              loading={loading || isPolling} 
              className="w-full relative"
              disabled={loading || isPolling}
            >
              {/* Animasi teks yang dinamis */}
              {isPolling ? "AI Sedang Melakukan Audit (Harap Tunggu)..." : loading ? "Mengunggah..." : "Verifikasi Sekarang"}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}