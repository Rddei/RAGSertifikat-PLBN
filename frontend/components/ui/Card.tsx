import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-[3px] border border-slate-300/70 bg-white p-6 shadow-[0_1px_2px_rgba(0,0,0,0.08)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
