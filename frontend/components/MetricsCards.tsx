import { Card } from "@/components/ui/Card";
import type { Metrics } from "@/lib/types";

export function MetricsCards({ metrics }: { metrics: Metrics }) {
  const items = [
    { label: "Total Pendaftar", value: metrics.total, color: "text-slate-900" },
    { label: "Diterima", value: metrics.diterima, color: "text-emerald-600" },
    { label: "Ditolak", value: metrics.ditolak, color: "text-red-600" },
    { label: "Terindikasi Fraud", value: metrics.fraud, color: "text-amber-600" },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {items.map((it) => (
        <Card key={it.label} className="p-4">
          <p className="text-sm text-slate-500">{it.label}</p>
          <p className={`mt-1 text-2xl font-bold ${it.color}`}>{it.value}</p>
        </Card>
      ))}
    </div>
  );
}
