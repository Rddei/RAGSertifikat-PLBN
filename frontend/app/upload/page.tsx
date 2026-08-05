"use client";

import { useState } from "react";
import { useRouter } from "next/navigation"; 
import { Navbar } from "@/components/Navbar";
import { FileUpload } from "@/components/FileUpload";
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
  const [isPolling, setIsPolling] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      toast.show("Pilih berkas terlebih dahulu.", "error");
      return;
    }
    
    setLoading(true);
    
    try {
      // 1. Tembak API Upload
      await api.verifyDocument(file, expectedName, jurusan);
      
      toast.show("Dokumen diterima! AI sedang menganalisis di latar belakang...", "success");
      setIsPolling(true);

      // 2. MEKANISME POLLING
      let attempts = 0;
      const maxAttempts = 20; 
      let isDone = false;

      while (attempts < maxAttempts && !isDone) {
        attempts++;
        
        await new Promise((resolve) => setTimeout(resolve, 3000));
        
        try {
          const res = await api.getApplicants();
          
          // PERBAIKAN: Antisipasi jika `res` berupa array langsung atau berada di dalam `res.data`
          const responseData = res?.data || res;
          
          // Pastikan data benar-benar bertipe Array sebelum menjalankan .find()
          const dataArray = Array.isArray(responseData) ? responseData : [];
          
          const processedDoc = dataArray.find(
            (doc: any) => doc.filename === file.name && doc.applicant_name === expectedName
          );

          if (processedDoc) {
            isDone = true;
            toast.show("Verifikasi Selesai! Mengalihkan ke hasil...", "success");
            router.push("/dashboard"); 
          }
        } catch (pollErr) {
          console.warn("Gagal mengecek status (Polling):", pollErr);
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
    <div className="min-h-screen pt-12 lg:pl-16">
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
                disabled={loading || isPolling}
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
              <FileUpload file={file} onSelect={setFile} disabled={loading || isPolling} />
            </div>
            
            <Button 
              type="submit" 
              loading={loading || isPolling} 
              className="w-full relative"
              disabled={loading || isPolling}
            >
              {isPolling ? "AI Sedang Melakukan Audit (Harap Tunggu)..." : loading ? "Mengunggah..." : "Verifikasi Sekarang"}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}