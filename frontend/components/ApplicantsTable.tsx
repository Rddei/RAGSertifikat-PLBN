"use client";

import { useState } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { cn, formatDate, scoreColor } from "@/lib/utils";
import { STATUS_OPTIONS, type Applicant } from "@/lib/types";

interface Props {
  applicants: Applicant[];
  onChanged: () => void;
}

export function ApplicantsTable({ applicants, onChanged }: Props) {
  const toast = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);

  async function handleOverride(id: number, status: string) {
    if (!status) return;
    setBusyId(id);
    try {
      await api.overrideStatus(id, status);
      toast.show("Status final diperbarui.", "success");
      onChanged();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Gagal memperbarui status.", "error");
    } finally {
      setBusyId(null);
    }
  }

  if (applicants.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        Belum ada data pendaftar.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-3 py-2">Nama</th>
            <th className="px-3 py-2">Jurusan</th>
            <th className="px-3 py-2">Skor</th>
            <th className="px-3 py-2">Status AI</th>
            <th className="px-3 py-2">Status Final</th>
            <th className="px-3 py-2">Tanggal</th>
            <th className="px-3 py-2">Ubah Status</th>
            <th className="px-3 py-2">Detail</th>
          </tr>
        </thead>
        <tbody>
          {applicants.map((a) => (
            <tr key={a.id} className="border-b border-slate-100 hover:bg-slate-50">
              <td className="px-3 py-2 font-medium">{a.applicant_name ?? "-"}</td>
              <td className="px-3 py-2 text-slate-600">{a.target_major ?? "-"}</td>
              <td className={cn("px-3 py-2 font-semibold", scoreColor(a.skor_kepatuhan))}>
                {a.skor_kepatuhan ?? "-"}
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={a.ai_status} />
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={a.final_status} />
              </td>
              <td className="px-3 py-2 text-slate-500">{formatDate(a.created_at)}</td>
              <td className="px-3 py-2">
                <select
                  disabled={busyId === a.id}
                  value={a.final_status ?? ""}
                  onChange={(e) => handleOverride(a.id, e.target.value)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs outline-none focus:border-brand-500 disabled:opacity-50"
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
              </td>
              <td className="px-3 py-2">
                <Link
                  href={`/applicants/${a.id}`}
                  className="text-brand-600 hover:underline"
                >
                  Lihat
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
