import type { Metrics } from "@/lib/types";

const BOXES = [
  { key: "total", label: "Total Pendaftar", bg: "bg-[#00c0ef]", icon: "\u{1F465}" },
  { key: "diterima", label: "Diterima", bg: "bg-[#00a65a]", icon: "\u2714" },
  { key: "ditolak", label: "Ditolak", bg: "bg-[#dd4b39]", icon: "\u2716" },
  { key: "fraud", label: "Terindikasi Fraud", bg: "bg-[#f39c12]", icon: "\u26A0" },
] as const;

export function MetricsCards({ metrics }: { metrics: Metrics }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {BOXES.map((b) => (
        <div key={b.key} className={`relative overflow-hidden rounded-[3px] text-white shadow-sm ${b.bg}`}>
          <div className="p-4">
            <p className="text-3xl font-bold leading-none">{metrics[b.key]}</p>
            <p className="mt-1 text-sm">{b.label}</p>
          </div>
          <span aria-hidden className="absolute -right-1 top-1 select-none text-6xl opacity-20">
            {b.icon}
          </span>
          <div className="bg-black/10 py-1 text-center text-xs">
            More info <span aria-hidden>&#10132;</span>
          </div>
        </div>
      ))}
    </div>
  );
}
