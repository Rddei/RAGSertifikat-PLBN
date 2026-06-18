"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { BatchStatus } from "@/lib/types";

const ALLOWED = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const MAX_MB = 20;
const DONE_STATES = ["selesai", "completed", "complete", "done", "success"];

export default function BatchPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const toast = useToast();
  const [files, setFiles] = useState<File[]>([]);
  const [names, setNames] = useState<string[]>([]);
  const [jurusan, setJurusan] = useState("");
  const [starting, setStarting] = useState(false);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [status, setStatus] = useState<BatchStatus | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const valid: File[] = [];
    for (const f of Array.from(list)) {
      if (!ALLOWED.includes(f.type)) {
        toast.show(`${f.name}: format tidak didukung.`, "error");
        continue;
      }
      if (f.size > MAX_MB * 1024 * 1024) {
        toast.show(`${f.name}: melebihi ${MAX_MB}MB.`, "error");
        continue;
      }
      valid.push(f);
    }
    setFiles((prev) => [...prev, ...valid]);
    setNames((prev) => [...prev, ...valid.map(() => "")]);
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setNames((prev) => prev.filter((_, i) => i !== index));
  }

  function setName(index: number, value: string) {
    setNames((prev) => prev.map((n, i) => (i === index ? value : n)));
  }

  const isDone = useCallback((s: BatchStatus | null) => {
    if (!s) return false;
    if (s.total > 0 && s.processed >= s.total) return true;
    return DONE_STATES.includes((s.status ?? "").toLowerCase());
  }, []);

  useEffect(() => {
    if (batchId === null) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const s = await api.getBatchStatus(batchId);
        if (!active) return;
        setStatus(s);
        if (isDone(s)) {
          toast.show("Batch selesai diproses.", "success");
          return;
        }
        timer = setTimeout(tick, 1500);
      } catch (e) {
        if (!active) return;
        toast.show(e instanceof Error ? e.message : "Gagal memantau batch.", "error");
      }
    };
    timer = setTimeout(tick, 800);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [batchId, isDone, toast]);

  async function handleStart() {
    if (files.length === 0) {
      toast.show("Tambahkan minimal satu berkas.", "error");
      return;
    }
    if (!jurusan.trim()) {
      toast.show("Isi jurusan tujuan.", "error");
      return;
    }
    setStarting(true);
    setStatus(null);
    try {
      const safeNames = names.map((n, i) => n.trim() || files[i].name);
      const res = await api.startBatch(files, safeNames, jurusan);
      setBatchId(res.batch_id);
      toast.show(`Batch #${res.batch_id} dimulai (${res.total_files} berkas).`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal memulai batch.", "error");
    } finally {
      setStarting(false);
    }
  }

  function reset() {
    setFiles([]);
    setNames([]);
    setJurusan("");
    setBatchId(null);
    setStatus(null);
  }

  if (!ready || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-brand-600" />
      </div>
    );
  }

  const pct =
    status && status.total > 0 ? Math.round((status.processed / status.total) * 100) : 0;
  const progressStyle = { width: `${pct}%` };
  const running = batchId !== null && !isDone(status);

  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <h1 className="text-2xl font-bold">Verifikasi Batch</h1>
        <p className="text-sm text-slate-500">
          Unggah banyak sertifikat sekaligus. Sistem memproses di latar belakang dan hasilnya
          muncul di Dashboard.
        </p>

        <Card className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Jurusan Tujuan</label>
            <Input
              value={jurusan}
              onChange={(e) => setJurusan(e.target.value)}
              placeholder="mis. Teknik Informatika"
              disabled={running}
            />
          </div>

          <div
            onClick={() => !running && inputRef.current?.click()}
            className="cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center transition hover:border-brand-400"
          >
            <p className="text-sm font-medium text-slate-700">Klik untuk menambah berkas</p>
            <p className="mt-1 text-xs text-slate-500">
              JPG, PNG, WEBP, atau PDF / maks {MAX_MB}MB per berkas
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={ALLOWED.join(",")}
              className="hidden"
              onChange={(e) => addFiles(e.target.files)}
            />
          </div>

          {files.length > 0 && (
            <ul className="space-y-2">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`} className="flex items-center gap-2">
                  <Input
                    value={names[i]}
                    onChange={(e) => setName(i, e.target.value)}
                    placeholder={`Nama pendaftar untuk ${f.name}`}
                    disabled={running}
                  />
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    disabled={running}
                    className="shrink-0 text-xs text-slate-500 transition hover:text-red-600 disabled:opacity-50"
                  >
                    Hapus
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex gap-2">
            <Button loading={starting} disabled={running} onClick={handleStart}>
              Mulai Batch ({files.length})
            </Button>
            {(batchId !== null || files.length > 0) && (
              <Button variant="ghost" onClick={reset} disabled={starting || running}>
                Reset
              </Button>
            )}
          </div>
        </Card>

        {status && (
          <Card className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Batch #{status.batch_id}</h2>
              <span className="text-sm text-slate-500">
                {status.processed}/{status.total} diproses
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-600 transition-all" style={progressStyle} />
            </div>
            <div className="flex items-center gap-2 text-sm">
              {running ? (
                <>
                  <Spinner className="h-4 w-4 text-brand-600" />
                  <span className="text-slate-600">Memproses...</span>
                </>
              ) : (
                <Link href="/dashboard" className="text-brand-600 hover:underline">
                  Selesai - lihat hasil di Dashboard &rarr;
                </Link>
              )}
            </div>
          </Card>
        )}
      </main>
    </div>
  );
}
