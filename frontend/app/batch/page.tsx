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

const ALLOWED = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const MAX_MB = 20;
const DONE_STATES = ["selesai", "completed", "complete", "done", "success"];
// Sama dengan aturan backend: <id 4+ digit>-<indeks 1..3>.<ext>
const FILENAME_PAT = /^\s*\d{4,}\s*-\s*[1-3](?:[\s._-].*)?\.(pdf|jpe?g|png|webp)\s*$/i;

export default function BatchPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const toast = useToast();
  const [files, setFiles] = useState<File[]>([]);
  const [starting, setStarting] = useState(false);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [status, setStatus] = useState<BatchStatus | null>(null);
  const [accepted, setAccepted] = useState<BatchAcceptedItem[]>([]);
  const [rejected, setRejected] = useState<BatchRejectedItem[]>([]);
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
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
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
    setStarting(true);
    setStatus(null);
    setAccepted([]);
    setRejected([]);
    try {
      const res = await api.startBatch(files);
      setBatchId(res.batch_id);
      setAccepted(res.accepted ?? []);
      setRejected(res.rejected ?? []);
      const tolak = res.rejected?.length ?? 0;
      toast.show(
        `Batch #${res.batch_id}: ${res.total_files} diproses` +
          (tolak > 0 ? `, ${tolak} ditolak` : ""),
        tolak > 0 ? "error" : "success",
      );
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal memulai batch.", "error");
    } finally {
      setStarting(false);
    }
  }

  function reset() {
    setFiles([]);
    setBatchId(null);
    setStatus(null);
    setAccepted([]);
    setRejected([]);
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
    <div className="min-h-screen pt-12 lg:pl-56">
      <Navbar />
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <h1 className="text-2xl font-bold">Verifikasi Batch</h1>
        <p className="text-sm text-slate-500">
          Cukup unggah berkas sertifikat. Nama pendaftar dan jurusan tujuan diambil
          otomatis dari master pendaftar berdasarkan nama file
          <span className="mx-1 rounded bg-slate-100 px-1 py-0.5 font-mono text-xs">
            id-indeks.ext
          </span>
          (contoh: <span className="font-mono text-xs">426161036-1.jpg</span>, maksimum 3
          sertifikat per pendaftar).
        </p>

        <Card className="space-y-4">
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
              {files.map((f, i) => {
                const patOk = FILENAME_PAT.test(f.name);
                return (
                  <li key={`${f.name}-${i}`} className="flex items-center gap-2 text-sm">
                    <span className="min-w-0 flex-1 truncate font-mono text-xs">{f.name}</span>
                    {!patOk && (
                      <span className="shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-[11px] text-amber-800">
                        nama file tidak sesuai format
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      disabled={running}
                      className="shrink-0 text-xs text-slate-500 transition hover:text-red-600 disabled:opacity-50"
                    >
                      Hapus
                    </button>
                  </li>
                );
              })}
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

        {rejected.length > 0 && (
          <Card className="space-y-2 border-amber-200 bg-amber-50">
            <h2 className="text-sm font-semibold text-amber-900">
              Ditolak di awal ({rejected.length})
            </h2>
            <ul className="space-y-1 text-xs text-amber-800">
              {rejected.map((r, i) => (
                <li key={`${r.filename}-${i}`}>
                  <span className="font-mono">{r.filename}</span> — {r.alasan}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {accepted.length > 0 && (
          <Card className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-700">
              Teridentifikasi ({accepted.length})
            </h2>
            <ul className="space-y-1 text-xs text-slate-600">
              {accepted.map((a, i) => (
                <li key={`${a.filename}-${i}`}>
                  <span className="font-mono">{a.filename}</span> &rarr; {a.nama}
                  <span className="text-slate-400"> · {a.jurusan}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}

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
