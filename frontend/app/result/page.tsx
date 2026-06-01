"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ComplianceResult from "@/components/ComplianceResult";
import { VerificationResult } from "@/lib/api";

export default function ResultPage() {
  const router = useRouter();
  const [data, setData] = useState<VerificationResult | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("verificationResult");
    if (stored) {
      setData(JSON.parse(stored));
      localStorage.removeItem("verificationResult");
    }
  }, []);

  if (!data) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Data tidak ditemukan. Silakan unggah ulang.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 text-center">Hasil Verifikasi</h1>
        <ComplianceResult data={data} />
        <button
          onClick={() => router.push("/")}
          className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          Verifikasi Dokumen Lain
        </button>
      </div>
    </main>
  );
}