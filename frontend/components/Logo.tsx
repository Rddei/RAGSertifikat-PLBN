import { cn } from "@/lib/utils";

// Logo resmi POLBAN dari berkas statis.
// Taruh berkas logo di: frontend/public/logo-polban.png
// (boleh .svg/.webp — sesuaikan src di bawah dengan nama berkasnya).
export function Logo({
  className,
  showText = true,
}: {
  className?: string;
  showText?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logo-polban.png"
        alt="Logo Politeknik Negeri Bandung"
        width={30}
        height={30}
        className="h-[30px] w-auto object-contain"
      />
      {showText && (
        <span className="leading-tight">
          <span className="font-semibold text-brand-700">POLBAN</span>{" "}
          <span className="font-normal text-slate-500">Compliance</span>
        </span>
      )}
    </span>
  );
}
