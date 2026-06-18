import { cn } from "@/lib/utils";

// Emblem POLBAN Compliance: perisai (keamanan/verifikasi) + centang emas (lolos audit).
export function Logo({
  className,
  showText = true,
}: {
  className?: string;
  showText?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path
          d="M16 2 4 7v7.5C4 21.6 9.1 27.5 16 30c6.9-2.5 12-8.4 12-15.5V7L16 2Z"
          fill="#1e3f8f"
        />
        <path
          d="M10 16.2l4 4 8-8.4"
          stroke="#f5b301"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
      {showText && (
        <span className="leading-tight">
          <span className="font-semibold text-brand-700">POLBAN</span>{" "}
          <span className="font-normal text-slate-500">Compliance</span>
        </span>
      )}
    </span>
  );
}
