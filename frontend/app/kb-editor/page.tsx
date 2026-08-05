"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";

export default function KbEditorPage() {
  const { ready, isAuthenticated, user } = useRequireAuth();
  const router = useRouter();
  const toast = useToast();

  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // Ambil isi Markdown dari backend saat halaman dimuat
  useEffect(() => {
    if (!ready || !isAuthenticated) return;

    // Proteksi: Jika bukan admin, tendang kembali ke Dashboard
    if (user && user.role !== "admin") {
      toast.show("Akses ditolak. Anda bukan Admin.", "error");
      router.replace("/dashboard");
      return;
    }

    const fetchKb = async () => {
      try {
        const res = await api.getKbContent();
        setContent(res.content);
      } catch (err) {
        toast.show(err instanceof Error ? err.message : "Gagal memuat aturan.", "error");
      } finally {
        setLoading(false);
      }
    };

    fetchKb();
  }, [ready, isAuthenticated, user, router, toast]);

  // Simpan hasil edit ke file markdown
  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateKbContent(content);
      toast.show("Aturan berhasil disimpan ke server!", "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Gagal menyimpan.", "error");
    } finally {
      setSaving(false);
    }
  };

  // Jalankan indexer ChromaDB di latar belakang
  const handleSyncAI = async () => {
    setSyncing(true);
    try {
      const res = await api.syncKb();
      toast.show(res.message || "Sinkronisasi AI berjalan di latar belakang...", "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Gagal menyinkronkan AI.", "error");
    } finally {
      setSyncing(false);
    }
  };

  if (!ready || !isAuthenticated || (user && user.role !== "admin")) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-12 lg:pl-16">
      <Navbar />
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Manajemen Aturan (Knowledge Base)</h1>
            <p className="text-sm text-slate-500">Edit kriteria kelulusan SNBP 2026. Data menggunakan format Markdown.</p>
          </div>
          <div className="flex space-x-3">
            <Button variant="outline" onClick={() => router.push("/dashboard")}>
              Kembali
            </Button>
            <Button variant="secondary" loading={syncing} onClick={handleSyncAI} title="Jalankan Ulang ChromaDB Indexer">
              🔄 Sinkronisasi AI
            </Button>
            <Button loading={saving} onClick={handleSave}>
              💾 Simpan Perubahan
            </Button>
          </div>
        </div>

        <Card className="p-0 overflow-hidden shadow-sm border border-slate-200">
          {loading ? (
            <div className="flex h-96 items-center justify-center">
              <Spinner className="h-8 w-8 text-indigo-600" />
            </div>
          ) : (
            <div className="relative">
              {/* Textarea untuk mengedit Markdown Murni */}
              <textarea
                className="h-[600px] w-full resize-y bg-slate-900 p-6 font-mono text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                spellCheck={false}
                placeholder="Tulis aturan kriteria SNBP dalam format Markdown di sini..."
              />
            </div>
          )}
        </Card>
        
        <div className="rounded-md bg-blue-50 p-4 border border-blue-200">
          <div className="flex">
            <div className="flex-shrink-0">
              <span className="text-xl">ℹ️</span>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">Instruksi Penting:</h3>
              <div className="mt-2 text-sm text-blue-700">
                <ul className="list-disc space-y-1 pl-5">
                  <li>Edit aturan sesuai format <strong>Markdown</strong> pada kotak hitam di atas.</li>
                  <li>Setelah selesai, tekan <strong>Simpan Perubahan</strong> agar file `.md` di server diperbarui.</li>
                  <li>Agar agen AI (Gemini/RAG) bisa mengenali aturan baru ini, Anda <strong>WAJIB menekan tombol Sinkronisasi AI</strong>. Sistem akan memperbarui memori vektor (ChromaDB) di latar belakang secara otomatis.</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}