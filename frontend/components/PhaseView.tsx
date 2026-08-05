"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { Applicant } from "@/lib/types";

/**
 * Menampilkan proses verifikasi sebagai 3 FASE dalam bentuk WIZARD:
 * satu fase ditampilkan pada satu waktu, dinavigasi dengan tombol
 * Sebelumnya / Selanjutnya. Data berasal dari hasil yang SUDAH tersimpan
 * (bukan real-time) -- tombol hanya membuka fase secara bertahap agar
 * mudah dijelaskan langkah demi langkah.
 */

type PhaseState = "pass" | "review" | "fail" | "skipped";

const STATE_STYLE: Record<PhaseState, { ring: string; badge: string; dot: string; label: string }> = {
  pass:    { ring: "border-green-300 bg-green-50", badge: "bg-green-100 text-green-800", dot: "bg-green-500", label: "Lolos" },
  review:  { ring: "border-amber-300 bg-amber-50", badge: "bg-amber-100 text-amber-800", dot: "bg-amber-500", label: "Perlu Tinjauan" },
  fail:    { ring: "border-red-300 bg-red-50",     badge: "bg-red-100 text-red-800",     dot: "bg-red-500",   label: "Gagal" },
  skipped: { ring: "border-gray-200 bg-gray-50",   badge: "bg-gray-100 text-gray-500",   dot: "bg-gray-300",  label: "Tidak dijalankan" },
};

function StepDot({ n, state, active }: { n: number; state: PhaseState; active: boolean }) {
  const s = STATE_STYLE[state];
  return (
    <div
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white transition-all",
        s.dot,
        active && "ring-4 ring-offset-1 ring-blue-200 scale-110",
      )}
    >
      {state === "pass" ? "\u2713" : state === "fail" ? "\u2715" : n}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex justify-between gap-3 py-1 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="text-right font-medium text-gray-800">{value}</span>
    </div>
  );
}

export function PhaseView({ a }: { a: Applicant }) {
  const [step, setStep] = useState(0);

  const adaEkstraksi = Boolean(a.nama_lomba || a.tingkat || a.nama_penyelenggara);
  const fase1: PhaseState = adaEkstraksi ? "pass" : "fail";

  const relStatus = a.kriteria_relevansi?.status ?? null;
  let fase2: PhaseState = "skipped";
  if (fase1 === "pass") {
    if (relStatus === "tercantum") fase2 = "pass";
    else if (relStatus === "tidak_tercantum") fase2 = "fail";
    else fase2 = "review";
  }

  const statusAkhir = (a.ai_status ?? "").toLowerCase();
  let fase3: PhaseState = "skipped";
  if (fase1 === "pass") {
    if (statusAkhir.includes("diterima")) fase3 = "pass";
    else if (statusAkhir.includes("ditolak")) fase3 = "fail";
    else fase3 = "review";
  }

  const skorPrestasi = a.skor_prestasi?.total ?? a.skor_prestasi?.total_parsial ?? null;
  const parsial = a.skor_prestasi?.total === null && a.skor_prestasi != null;

  const phases = [
    {
      n: 1,
      title: "Ekstraksi & Penyaringan",
      state: fase1,
      rows: (
        <>
          <Row label="Jenis" value={adaEkstraksi ? "Sertifikat prestasi (lolos gerbang)" : "Bukan sertifikat prestasi"} />
          <Row label="Nama Lomba" value={a.nama_lomba} />
          <Row label="Tingkat" value={a.tingkat} />
          <Row label="Kategori" value={a.kategori} />
          <Row label="Penyelenggara" value={a.nama_penyelenggara} />
          <Row label="Kurasi SIMT" value={a.kurasi_status} />
          {a.kurasi_ajang_terdekat && <Row label="Ajang Terdekat" value={a.kurasi_ajang_terdekat} />}
        </>
      ),
    },
    {
      n: 2,
      title: "Identitas & Relevansi",
      state: fase2,
      rows: (
        <>
          <Row label="ID Pendaftaran" value={a.id_pendaftaran} />
          <Row label="Nama (Pendaftar)" value={a.applicant_name} />
          <Row label="Nama (Sertifikat)" value={a.nama_peserta} />
          <Row label="Jurusan Tujuan" value={a.target_major} />
          <Row label="Jenjang" value={a.kriteria_relevansi?.jenjang} />
          <Row label="Status Relevansi" value={a.kriteria_relevansi?.status} />
          {a.kriteria_relevansi?.item_terdekat && <Row label="Item Terdekat" value={a.kriteria_relevansi.item_terdekat} />}
        </>
      ),
    },
    {
      n: 3,
      title: "Penilaian",
      state: fase3,
      rows: (
        <>
          <Row label="Skor Prestasi" value={skorPrestasi !== null ? `${skorPrestasi}${parsial ? " (parsial)" : ""}` : "-"} />
          {a.skor_prestasi?.bidang && <Row label="Bidang" value={`${a.skor_prestasi.bidang} (${a.skor_prestasi.poin_bidang ?? "-"})`} />}
          {a.skor_prestasi?.tingkat && <Row label="Tingkat" value={`${a.skor_prestasi.tingkat} (${a.skor_prestasi.poin_tingkat ?? "-"})`} />}
          {a.skor_prestasi?.partisipasi && <Row label="Individu/Kelompok" value={`${a.skor_prestasi.partisipasi} (${a.skor_prestasi.poin_partisipasi ?? "-"})`} />}
          <Row label="Skor Kepatuhan" value={a.skor_kepatuhan != null ? `${a.skor_kepatuhan}/100` : null} />
          <Row label="Status Sistem" value={a.ai_status} />
        </>
      ),
    },
  ];

  const current = phases[step];
  const s = STATE_STYLE[current.state];

  return (
    <div className="space-y-4">
      <div className="flex items-center">
        {phases.map((p, i) => (
          <div key={p.n} className={cn("flex items-center", i < phases.length - 1 && "flex-1")}>
            <button type="button" onClick={() => setStep(i)} className="flex flex-col items-center gap-1" aria-label={`Fase ${p.n}`}>
              <StepDot n={p.n} state={p.state} active={i === step} />
              <span className={cn("text-xs", i === step ? "font-semibold text-gray-800" : "text-gray-400")}>Fase {p.n}</span>
            </button>
            {i < phases.length - 1 && (
              <div className={cn("mx-1 mb-4 h-0.5 flex-1", i < step ? "bg-blue-400" : "bg-gray-200")} />
            )}
          </div>
        ))}
      </div>

      <div className={cn("rounded-lg border p-5 transition-all", s.ring)}>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StepDot n={current.n} state={current.state} active />
            <h3 className="text-base font-semibold text-gray-800">Fase {current.n} — {current.title}</h3>
          </div>
          <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", s.badge)}>{s.label}</span>
        </div>
        <div className="pl-11">{current.rows}</div>
      </div>

      <div className="flex items-center justify-between">
        <button type="button" onClick={() => setStep((v) => Math.max(0, v - 1))} disabled={step === 0}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40">
          ← Sebelumnya
        </button>
        <span className="text-xs text-gray-400">Fase {step + 1} dari {phases.length}</span>
        <button type="button" onClick={() => setStep((v) => Math.min(phases.length - 1, v + 1))} disabled={step === phases.length - 1}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40">
          Selanjutnya →
        </button>
      </div>
    </div>
  );
}