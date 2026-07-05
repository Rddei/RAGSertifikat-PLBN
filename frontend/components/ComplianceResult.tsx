import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { ReasoningView } from "@/components/ReasoningView";
import { SimtFlags } from "@/components/SimtFlags";
import { cn, scoreColor } from "@/lib/utils";
import type { VerifyResponse } from "@/lib/types";

export function ComplianceResult({ result }: { result: VerifyResponse }) {
  const { audit, security, metadata, extraction, flags } = result;
  const score = audit.skor_kepatuhan ?? 0;
  const scoreStyle = { width: `${Math.max(0, Math.min(100, score))}%` };
  const extractionEntries = Object.entries(extraction ?? {});

  return (
    <Card className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Hasil Verifikasi</h2>
          <p className="text-sm text-slate-500">{metadata.filename}</p>
        </div>
        <StatusBadge status={audit.status} />
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between text-sm">
          <span className="text-slate-600">Skor Kepatuhan</span>
          <span className={cn("font-semibold", scoreColor(score))}>{score}/100</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-indigo-500" style={scoreStyle} />
        </div>
      </div>

      {flags && <SimtFlags flags={flags} />}

      {audit.langkah_gagal && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          <span className="font-medium">Langkah gagal: </span>
          {audit.langkah_gagal}
        </div>
      )}

      <div>
        <h3 className="mb-2 text-sm font-medium text-slate-700">Alasan Audit</h3>
        <ReasoningView text={audit.reasoning} />
      </div>

      {security.fraud_flags.length > 0 && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
          <p className="font-medium">Indikasi kecurangan:</p>
          <ul className="ml-4 mt-1 list-disc space-y-0.5">
            {security.fraud_flags.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {extractionEntries.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-slate-700">Data Terekstrak</h3>
          <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {extractionEntries.map(([k, v]) => (
              <div key={k} className="rounded-lg bg-slate-50 p-2">
                <dt className="text-xs uppercase tracking-wide text-slate-400">{k}</dt>
                <dd className="text-sm text-slate-700">{String(v ?? "") || "-"}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </Card>
  );
}
