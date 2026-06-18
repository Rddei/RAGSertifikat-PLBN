"use client";

import { useState } from "react";
import { Navbar } from "@/components/Navbar";
import { FileUpload } from "@/components/FileUpload";
import { ComplianceResult } from "@/components/ComplianceResult";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { VerifyResponse } from "@/lib/types";

export default function UploadPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [expectedName, setExpectedName] = useState("");
  const [jurusan, setJurusan] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VerifyResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      toast.show("Pilih berkas terlebih dahulu.", "error");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await api.verifyDocument(file, expectedName, jurusan);
      setResult(res);
      toast.show("Verifikasi selesai.", "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Verifikasi gagal.", "error");
    } finally {
      setLoading(false);
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
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Berkas Sertifikat
              </label>
              <FileUpload file={file} onSelect={setFile} />
            </div>
            <Button type="submit" loading={loading} className="w-full">
              Verifikasi Sekarang
            </Button>
          </form>
        </Card>
        {result && <ComplianceResult result={result} />}
      </main>
    </div>
  );
}
