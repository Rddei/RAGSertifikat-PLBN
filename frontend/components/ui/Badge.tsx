import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Color = "slate" | "green" | "red" | "amber";

const colorStyles: Record<Color, string> = {
  slate: "bg-slate-100 text-slate-700",
  green: "bg-emerald-100 text-emerald-700",
  red: "bg-red-100 text-red-700",
  amber: "bg-amber-100 text-amber-700",
};

export function Badge({
  color = "slate",
  children,
}: {
  color?: Color;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        colorStyles[color],
      )}
    >
      {children}
    </span>
  );
}
