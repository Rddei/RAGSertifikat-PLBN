import { Badge } from "@/components/ui/Badge";

export function StatusBadge({ status }: { status: string | null }) {
  const s = (status ?? "").toLowerCase();
  if (s.includes("diterima")) return <Badge color="green">{status}</Badge>;
  if (s.includes("ditolak")) return <Badge color="red">{status}</Badge>;
  if (s.includes("tinjauan")) return <Badge color="amber">{status}</Badge>;
  return <Badge color="slate">{status ?? "-"}</Badge>;
}

export function KurasiBadge({ status }: { status: string | null }) {
  const s = (status ?? "").toLowerCase();
  if (s.includes("terkurasi") && !s.includes("tidak"))
    return <Badge color="green">{status}</Badge>;
  if (s.includes("perlu")) return <Badge color="amber">{status}</Badge>;
  if (s.includes("tidak terkurasi")) return <Badge color="red">{status}</Badge>;
  return <Badge color="slate">{status ?? "-"}</Badge>;
}
