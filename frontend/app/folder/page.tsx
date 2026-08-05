"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { BatchAcceptedItem, BatchRejectedItem, BatchStatus } from "@/lib/types";

const DONE_STATES = ["selesai", "completed", "complete", "done", "success"];

export default function FolderPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const toast = useToast();

  const [subfolder, setSubfolder] = useState("");
  const [starting, setStarting] = useState(false);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [status, setStatus] = useState<BatchStatus | null>(null);
  const [accepted, setAccepted] = useState<BatchAcceptedItem[]>([]);
  const [rejected, setRejected] = useState<BatchRejectedItem[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isDone = useCallback((s: BatchStatus | null) => {
    if (!s) return false;
    return DONE_STATES.includes((s.status ?? "").toLowerCase());
  }, []);

  // Polling status batch (dipakai ulang dari endpoint status batch yang sama).
  useEffect(() => {
    if (batchId === null) return;
    const tick = async () => {
      try {
        const s = await api.getBatchStatus(batchId);
        setStatus(s);
        if (isDone(s) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (e) {
        toast.show(e instanceof Error ? e.message : "Gagal memantau proses.", "error");
      }
    };
    tick();
    pollRef.current = setInterval(tick, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [batchId, isDone, toast]);

  const handleStart = async () => {
    setStarting(true);
    setStatus(null);
    setAccepted([]);
    setRejected([]);
    setBatchId(null);
    try {
      const res = await api.startFolderIngest(subfolder.trim());
      setBatchId(res.batch_id);
      setAccepted(res.accepted ?? []);
      setRejected(res.rejected ?? []);
      toast.show(
        `Impor folder dimulai (Batch #${res.batch_id}): ${res.total_files} berkas diproses.`,
        "success",
      );
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal memulai impor folder.", "error");
    } finally {
      setStarting(false);
    }
  };

  if (!ready || !isAuthenticated) return null;

  const pct =
    status && status.total > 0 ? Math.round((status.processed / status.total) * 100) : 0;
  const running = batchId !== null && !isDone(status);

  return (
    <div className="min-h-screen bg-gray-50 pt-12 lg:pl-16">
      <Navbar />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Impor dari Folder Server</h1>
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">
            ← Kembali ke Dashboard
          </Link>
        </div>

        <Card className="p-6">
          <p className="mb-4 text-sm text-gray-600">
            Memproses berkas sertifikat yang sudah berada pada folder di server.
            Berkas harus dinamai <code className="rounded bg-gray-100 px-1">
            &lt;id_pendaftaran&gt;-&lt;indeks&gt;.&lt;ekstensi&gt;</code> (mis.{" "}
            <code className="rounded bg-gray-100 px-1">221524015-1.pdf</code>).
            Identitas dan jurusan di-lookup otomatis dari master pendaftar.
          </p>

          <label className="mb-2 block text-sm font-medium text-gray-700">
            Subfolder (opsional)
          </label>
          <input
            type="text"
            value={subfolder}
            onChange={(e) => setSubfolder(e.target.value)}
            placeholder="kosongkan untuk membaca folder utama"
            disabled={starting || running}
            className="mb-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
          />

          <Button onClick={handleStart} disabled={starting || running}>
            {starting ? (
              <span className="flex items-center gap-2">
                <Spinner /> Memulai…
              </span>
            ) : (
              "Mulai Impor Folder"
            )}
          </Button>
        </Card>

        {status && (
          <Card className="mt-6 p-6">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium text-gray-700">
                Batch #{batchId} — {running ? "memproses…" : "selesai"}
              </span>
              <span className="text-gray-500">
                {status.processed}/{status.total} berkas
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
              <div
                className="h-full rounded-full bg-blue-600 transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            {!running && (
              <p className="mt-3 text-sm text-green-700">
                Pemrosesan selesai. Lihat hasilnya di{" "}
                <Link href="/dashboard" className="underline">Dashboard</Link>.
              </p>
            )}
          </Card>
        )}

        {(accepted.length > 0 || rejected.length > 0) && (
          <Card className="mt-6 p-6">
            {accepted.length > 0 && (
              <div className="mb-4">
                <h3 className="mb-2 text-sm font-semibold text-green-700">
                  Diterima ({accepted.length})
                </h3>
                <ul className="space-y-1 text-sm text-gray-700">
                  {accepted.map((a, i) => (
                    <li key={i} className="flex justify-between rounded bg-green-50 px-3 py-1.5">
                      <span>{a.filename}</span>
                      <span className="text-gray-500">
                        {a.nama} · {a.jurusan}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {rejected.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-red-700">
                  Ditolak ({rejected.length})
                </h3>
                <ul className="space-y-1 text-sm text-gray-700">
                  {rejected.map((r, i) => (
                    <li key={i} className="rounded bg-red-50 px-3 py-1.5">
                      <span className="font-medium">{r.filename}</span>
                      <span className="text-gray-500"> — {r.alasan}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        )}
      </main>
    </div>
  );
}