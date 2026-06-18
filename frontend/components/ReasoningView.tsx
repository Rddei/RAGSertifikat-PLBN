import { cn } from "@/lib/utils";

/**
 * Menampilkan teks "reasoning" dari auditor AI secara rapi.
 *
 * Teks dari LLM bisa datang dalam beberapa bentuk:
 *  (a) Markdown bernomor:
 *        1. **Label:** penjelasan ...
 *           * **Sub-aspek:** ...
 *        **Kesimpulan:** ...
 *  (b) Teks polos berlabel (tanpa markdown):
 *        Pencocokan nama: ... Anti-kecurangan: ... Prestasi: ...
 *
 * Komponen ini menangani KEDUA bentuk: jika tidak ada pola markdown bernomor,
 * ia akan memecah teks berdasarkan label "Sesuatu:" di awal kalimat. Dengan
 * begitu tampilan tetap rapi apa pun format keluaran AI. Tanpa pustaka eksternal.
 */

type Status = "pass" | "fail" | "review" | "neutral";

function statusOf(text: string): Status {
  const t = text.toLowerCase();
  // Urutan penting: cek "review" lalu "fail" sebelum "pass",
  // karena "tidak terpenuhi" mengandung kata "terpenuhi".
  if (/tinjauan manual|perlu ditinjau|tidak dapat memverifikasi|tidak dapat diverifikasi|belum dapat dipastikan|memerlukan informasi|perlu informasi|diperlukan tinjauan/.test(t)) {
    return "review";
  }
  if (/tidak terpenuhi|tidak sesuai|tidak diakui|tidak relevan|tidak cocok|tidak memenuhi|ditolak|wajib ditolak/.test(t)) {
    return "fail";
  }
  if (/terpenuhi|sesuai|relevan|cocok|bersih|diterima|valid|memenuhi|diakui/.test(t)) {
    return "pass";
  }
  return "neutral";
}

/** Render **tebal** menjadi <strong>, sisanya teks biasa. */
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    nodes.push(
      <strong key={key++} className="font-semibold text-slate-800">
        {m[1]}
      </strong>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path fillRule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 111.42-1.42l2.79 2.79 6.79-6.79a1 1 0 011.42 0z" clipRule="evenodd" />
    </svg>
  );
}

function CrossIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path fillRule="evenodd" d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" clipRule="evenodd" />
    </svg>
  );
}

function WarnIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.515 2.625H3.72c-1.345 0-2.188-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
    </svg>
  );
}

function DotIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <circle cx="10" cy="10" r="3" />
    </svg>
  );
}

function StatusIcon({ status }: { status: Status }) {
  const base = "h-3.5 w-3.5";
  if (status === "pass") return <CheckIcon className={cn(base, "text-emerald-600")} />;
  if (status === "fail") return <CrossIcon className={cn(base, "text-red-600")} />;
  if (status === "review") return <WarnIcon className={cn(base, "text-amber-500")} />;
  return <DotIcon className={cn(base, "text-slate-400")} />;
}

type Bullet = { label?: string; text: string; status: Status };
type Item = { num: string; title: string; mainText: string; mainStatus: Status; bullets: Bullet[] };

/** Parse satu poin bernomor markdown: "1. **Label:** ... * **Sub:** ..." */
function parseNumberedItem(raw: string): Item {
  const numMatch = raw.match(/^(\d+)\.\s+/);
  const num = numMatch ? numMatch[1] : "";
  let rest = numMatch ? raw.slice(numMatch[0].length) : raw;

  const titleMatch = rest.match(/^\*\*(.+?)\*\*:?\s*/);
  const title = titleMatch ? titleMatch[1].replace(/:$/, "") : "";
  rest = titleMatch ? rest.slice(titleMatch[0].length) : rest;

  const segs = rest
    .split(/(?=\*\s+\*\*)/)
    .map((s) => s.trim())
    .filter(Boolean);

  let mainText = "";
  const bullets: Bullet[] = [];
  for (const seg of segs) {
    if (/^\*\s+\*\*/.test(seg)) {
      const s = seg.replace(/^\*\s+/, "");
      const lbl = s.match(/^\*\*(.+?)\*\*:?\s*/);
      const label = lbl ? lbl[1].replace(/:$/, "") : undefined;
      const text = lbl ? s.slice(lbl[0].length).trim() : s;
      bullets.push({ label, text, status: statusOf(seg) });
    } else {
      mainText += (mainText ? " " : "") + seg;
    }
  }

  return { num, title, mainText, mainStatus: statusOf(mainText || title), bullets };
}

/**
 * Pecah teks polos berlabel menjadi item, mis.
 * "Pencocokan nama: ... Anti-kecurangan: ... Prestasi: ...".
 * Label = frasa pendek (1-6 kata) diawali huruf kapital di awal kalimat,
 * diikuti tanda titik dua.
 */
function splitByLabels(body: string): Item[] {
  const labelRe = /(^|\.\s+|\n+)([A-ZÀ-Ý][^.:\n]{1,45}?):\s+/g;
  const found: Array<{ label: string; start: number; contentStart: number }> = [];
  let m: RegExpExecArray | null;
  while ((m = labelRe.exec(body)) !== null) {
    found.push({
      label: m[2].trim(),
      start: m.index + m[1].length,
      contentStart: labelRe.lastIndex,
    });
  }
  // Perlu minimal 2 label agar dianggap terstruktur.
  if (found.length < 2) return [];

  const items: Item[] = [];
  for (let i = 0; i < found.length; i++) {
    const cur = found[i];
    const end = i + 1 < found.length ? found[i + 1].start : body.length;
    const text = body.slice(cur.contentStart, end).trim().replace(/\s+/g, " ");
    items.push({
      num: String(i + 1),
      title: cur.label,
      mainText: text,
      mainStatus: statusOf(text),
      bullets: [],
    });
  }
  return items;
}

function parseReasoning(raw: string) {
  const text = raw.replace(/\r\n/g, "\n").trim();

  // Pisahkan bagian kesimpulan bila ada.
  let body = text;
  let conclusion = "";
  const conc =
    text.match(/\*\*\s*Kesimpulan\s*:?\s*\*\*\s*/i) ||
    text.match(/(?:^|\.\s+|\n+)Kesimpulan\s*:\s*/i);
  if (conc && conc.index !== undefined) {
    const cut = conc.index + (conc[0].match(/^(?:\.\s+|\n+)/) ? conc[0].length : conc[0].length);
    body = text.slice(0, conc.index).trim();
    conclusion = text.slice(cut).trim();
  }

  // 1) Coba format markdown bernomor "1. **", "2. **", ...
  let items = body
    .split(/(?=\b\d+\.\s+\*\*)/)
    .map((s) => s.trim())
    .filter((s) => /^\d+\.\s+\*\*/.test(s))
    .map(parseNumberedItem);

  // 2) Bila tidak ada, coba pecah berdasarkan label teks polos.
  if (items.length === 0) {
    items = splitByLabels(body);
  }

  const fallback = items.length === 0 ? body : "";
  return { items, fallback, conclusion };
}

export function ReasoningView({ text, className }: { text: string; className?: string }) {
  if (!text?.trim()) {
    return <p className="text-sm text-slate-400">Tidak ada alasan.</p>;
  }

  const { items, fallback, conclusion } = parseReasoning(text);
  const concStatus: Status = conclusion ? statusOf(conclusion) : "neutral";

  return (
    <div className={cn("space-y-3", className)}>
      {items.length > 0 && (
        <ol className="space-y-2.5">
          {items.map((it, i) => (
            <li key={i} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3">
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-brand-600 text-[11px] font-semibold text-white">
                  {it.num}
                </span>
                <div className="min-w-0 flex-1">
                  {it.title && (
                    <div className="flex items-center gap-1.5">
                      <StatusIcon status={it.mainStatus} />
                      <p className="text-sm font-semibold text-slate-800">{it.title}</p>
                    </div>
                  )}
                  {it.mainText && (
                    <p className="mt-1 text-sm leading-relaxed text-slate-600">
                      {renderInline(it.mainText)}
                    </p>
                  )}
                  {it.bullets.length > 0 && (
                    <ul className="mt-2 space-y-1.5">
                      {it.bullets.map((b, j) => (
                        <li key={j} className="flex items-start gap-1.5">
                          <span className="mt-0.5 flex-none">
                            <StatusIcon status={b.status} />
                          </span>
                          <p className="text-sm leading-relaxed text-slate-600">
                            {b.label && (
                              <span className="font-medium text-slate-700">{b.label}: </span>
                            )}
                            {renderInline(b.text)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}

      {fallback && (
        <p className="text-sm leading-relaxed text-slate-600">{renderInline(fallback)}</p>
      )}

      {conclusion && (
        <div
          className={cn(
            "flex items-start gap-2 rounded-lg border p-3",
            concStatus === "pass" && "border-emerald-200 bg-emerald-50",
            concStatus === "fail" && "border-red-200 bg-red-50",
            concStatus === "review" && "border-amber-200 bg-amber-50",
            concStatus === "neutral" && "border-slate-200 bg-slate-50",
          )}
        >
          <span className="mt-0.5 flex-none">
            <StatusIcon status={concStatus} />
          </span>
          <div>
            <p
              className={cn(
                "text-xs font-semibold uppercase tracking-wide",
                concStatus === "pass" && "text-emerald-700",
                concStatus === "fail" && "text-red-700",
                concStatus === "review" && "text-amber-700",
                concStatus === "neutral" && "text-slate-600",
              )}
            >
              Kesimpulan
            </p>
            <p className="mt-0.5 text-sm leading-relaxed text-slate-700">
              {renderInline(conclusion)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
