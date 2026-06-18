"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/StatusBadge";
import { ReasoningView } from "@/components/ReasoningView";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { cn, formatDate, scoreColor } from "@/lib/utils";
import { STATUS_OPTIONS, type Applicant } from "@/lib/types";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-700">{value}</dd>
    </div>
  );
}

export default function ApplicantDetailPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const params = useParams();
  const toast = useToast();
  const id = Number(params?.id);
  const [applicant, setApplicant] = useState<Applicant | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await api.getApplicants();
      setApplicant(all.find((a) => a.id === id) ?? null);
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal memuat data.", "error");
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  useEffect(() => {
    if (ready && isAuthenticated) load();
  }, [ready, isAuthenticated, load]);

  async function handleOverride(status: string) {
    if (!status || !applicant) return;
    setBusy(true);
    try {
      await api.overrideStatus(applicant.id, status);
      toast.show("Status final diperbarui.", "success");
      load();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal memperbarui status.", "error");
    } finally {
      setBusy(false);
    }
  }

  if (!ready || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-brand-600" />
      </div>
    );
  }

  const scorePct = Math.max(0, Math.min(100, applicant?.skor_kepatuhan ?? 0));
  const scoreStyle = { width: `${scorePct}%` };
  const batchLabel = applicant?.batch_id ? `#${applicant.batch_id}` : "-";

  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Detail Pendaftar</h1>
          <Link href="/dashboard" className="text-sm text-brand-600 hover:underline">
            &larr; Kembali
          </Link>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <Spinner className="h-8 w-8 text-brand-600" />
          </div>
        ) : !applicant ? (
          <Card>
            <p className="text-sm text-slate-500">Data pendaftar tidak ditemukan.</p>
          </Card>
        ) : (
          <Card className="space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold">{applicant.applicant_name ?? "-"}</h2>
                <p className="text-sm text-slate-500">{applicant.filename}</p>
              </div>
              <StatusBadge status={applicant.final_status ?? applicant.ai_status} />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-slate-600">Skor Kepatuhan</span>
                <span className={cn("font-semibold", scoreColor(applicant.skor_kepatuhan))}>
                  {applicant.skor_kepatuhan ?? "-"}/100
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-brand-600" style={scoreStyle} />
              </div>
            </div>

            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Jurusan Tujuan" value={applicant.target_major ?? "-"} />
              <Field label="Status AI" value={applicant.ai_status ?? "-"} />
              <Field label="Batch" value={batchLabel} />
              <Field label="Tanggal" value={formatDate(applicant.created_at)} />
            </dl>

            {applicant.reasoning && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-slate-700">Alasan Audit</h3>
                <ReasoningView text={applicant.reasoning} />
              </div>
            )}

            {applicant.fraud_flags.length > 0 && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
                <p className="font-medium">Indikasi kecurangan:</p>
                <ul className="ml-4 mt-1 list-disc space-y-0.5">
                  {applicant.fraud_flags.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            {applicant.qr_data.length > 0 && (
              <div>
                <h3 className="mb-1 text-sm font-medium text-slate-700">Data QR</h3>
                <ul className="ml-4 list-disc space-y-0.5 text-sm text-slate-600">
                  {applicant.qr_data.map((q, i) => (
                    <li key={i} className="break-all">{q}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="border-t border-slate-100 pt-4">
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Ubah Status Final
              </label>
              <select
                disabled={busy}
                value={applicant.final_status ?? ""}
                onChange={(e) => handleOverride(e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 disabled:opacity-50"
              >
                <option value="" disabled>
                  Pilih...
                </option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </Card>
        )}
      </main>
    </div>
  );
}
