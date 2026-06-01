"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import FileUpload from "@/components/FileUpload";
import LoadingSpinner from "@/components/LoadingSpinner";
import ErrorMessage from "@/components/ErrorMessage";
import { verifyDocument } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [expectedName, setExpectedName] = useState("");
  const [jurusan, setJurusan] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!file || !expectedName.trim() || !jurusan.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const result = await verifyDocument(file, expectedName.trim(), jurusan.trim());
      localStorage.setItem("verificationResult", JSON.stringify(result));
      router.push("/result");
    } catch (err: any) {
      setError(err.message || "Terjadi kesalahan yang tidak diketahui");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Intelligent Compliance Engine</h1>
          <p className="text-gray-600 mt-2">Verifikasi Sertifikat Prestasi POLBAN</p>
        </div>

        <FileUpload onFileSelect={setFile} selectedFile={file} />

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nama Pendaftar</label>
            <input
              type="text"
              value={expectedName}
              onChange={(e) => setExpectedName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Masukkan nama lengkap"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Jurusan Tujuan</label>
            <input
              type="text"
              value={jurusan}
              onChange={(e) => setJurusan(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Contoh: Teknik Informatika"
            />
          </div>
        </div>

        {error && <ErrorMessage message={error} onRetry={() => setError(null)} />}

        {loading ? (
          <LoadingSpinner />
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!file || !expectedName.trim() || !jurusan.trim()}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            Verifikasi
          </button>
        )}
      </div>
    </main>
  );
}