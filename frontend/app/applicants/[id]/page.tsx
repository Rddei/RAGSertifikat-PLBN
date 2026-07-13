"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge, KurasiBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/Badge";
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

// Render satu entri penandatangan "Nama (Jabatan)" -> nama tebal, jabatan abu-abu.
function renderSignatory(text: string) {
  const m = text.match(/^(.*?)\s*\(([^)]*)\)\s*$/);
  if (m) {
    return (
      <>
        <span className="font-medium text-slate-800">{m[1]}</span>{" "}
        <span className="text-slate-500">({m[2]})</span>
      </>
    );
  }
  return text;
}

// Tampilkan penandatangan sebagai poin-poin (dipisah ";"). Bentang penuh 2 kolom.
function SignatoriesField({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  const items = (value || "")
    .split(/\s*;\s*/)
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div className="rounded-lg bg-slate-50 p-3 sm:col-span-2">
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      {items.length === 0 ? (
        <dd className="mt-0.5 text-sm text-slate-700">-</dd>
      ) : items.length === 1 ? (
        <dd className="mt-0.5 text-sm text-slate-700">{renderSignatory(items[0])}</dd>
      ) : (
        <dd className="mt-1">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {items.map((item, i) => (
              <li key={i}>{renderSignatory(item)}</li>
            ))}
          </ul>
        </dd>
      )}
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

            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-700">Data Sertifikat</h3>
              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="Nama di Sertifikat" value={applicant.nama_peserta || "-"} />
                <Field label="Nama Lomba" value={applicant.nama_lomba || "-"} />
                <Field label="Singkatan" value={applicant.singkatan_lomba || "-"} />
                <Field label="Penyelenggara" value={applicant.nama_penyelenggara || "-"} />
                <Field label="Kategori" value={applicant.kategori || "-"} />
                <Field label="Tingkat" value={applicant.tingkat || "-"} />
                <Field label="Peringkat" value={applicant.peringkat || "-"} />
                <Field label="Tanggal Kegiatan" value={applicant.tanggal_kegiatan || "-"} />
                <Field label="No. Sertifikat" value={applicant.nomor_sertifikat || "-"} />
                <SignatoriesField label="Penandatangan" value={applicant.penandatangan} />
              </dl>

              {applicant.url_verifikasi && (
                <p className="mt-2 text-sm">
                  <span className="text-slate-500">URL Verifikasi: </span>
                  <a
                    href={applicant.url_verifikasi}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-brand-600 hover:underline"
                  >
                    {applicant.url_verifikasi}
                  </a>
                </p>
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-xs uppercase tracking-wide text-slate-400">
                  Pemeriksaan:
                </span>
                <Badge color={applicant.ada_cap ? "green" : "slate"}>
                  {applicant.ada_cap ? "Ada Cap \u2713" : "Cap tidak terdeteksi \u2717"}
                </Badge>
                <Badge color={applicant.ada_ttd ? "green" : "slate"}>
                  {applicant.ada_ttd ? "Ada TTD \u2713" : "TTD tidak terdeteksi \u2717"}
                </Badge>
              </div>

              {applicant.deskripsi_cap &&
                (() => {
                  const caps = applicant.deskripsi_cap
                    .split(/\s*;\s*/)
                    .map((s) => s.trim())
                    .filter(Boolean);
                  return (
                    <div className="mt-2 text-sm text-slate-600">
                      <span className="text-slate-500">Deskripsi cap:</span>
                      {caps.length <= 1 ? (
                        <span> {applicant.deskripsi_cap}</span>
                      ) : (
                        <ul className="mt-1 list-disc space-y-1 pl-5">
                          {caps.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })()}
            </div>

            {applicant.kurasi_status && (
              <div className="rounded-lg border border-slate-200 p-3">
                <div className="mb-1 flex items-center justify-between">
                  <h3 className="text-sm font-medium text-slate-700">Kurasi SIMT</h3>
                  <KurasiBadge status={applicant.kurasi_status} />
                </div>
                {applicant.kurasi_ajang_terdekat ? (
                  <p className="text-sm text-slate-600">
                    Kandidat terdekat:{" "}
                    <span className="font-medium">{applicant.kurasi_ajang_terdekat}</span>{" "}
                    (skor nama {applicant.kurasi_skor_nama ?? "-"}, penyelenggara{" "}
                    {applicant.kurasi_skor_penyelenggara ?? "-"}).
                  </p>
                ) : (
                  <p className="text-sm text-slate-500">
                    Tidak ada padanan di daftar terkurasi SIMT.
                  </p>
                )}
                <p className="mt-1 text-xs text-slate-400">
                  Penanda informatif untuk verifikator; tidak memengaruhi skor.
                </p>
              </div>
            )}

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
