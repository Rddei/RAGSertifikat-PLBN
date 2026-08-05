"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";

const links = [
  { href: "/dashboard", label: "Dashboard", icon: "\u2302" },
  { href: "/batch", label: "Unggah Batch", icon: "\u2913" },
  { href: "/folder", label: "Impor Folder", icon: "\u2637" },
  { href: "/upload", label: "Verifikasi Satuan", icon: "\u2714" },
  { href: "/kb-editor", label: "Basis Pengetahuan", icon: "\u270E" },
];

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);   // mobile drawer
  const [hover, setHover] = useState(false);  // desktop hover-expand

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  // Lebar sidebar di desktop: menyempit (icon) normal, melebar saat hover.
  const expanded = hover;

  return (
    <>
      {/* Topbar oranye — offset kiri mengikuti lebar sidebar */}
      <header
        className={cn(
          "fixed top-0 right-0 left-0 z-40 flex h-12 items-center justify-between bg-[#f39c12] pr-4 transition-all",
          expanded ? "lg:left-56" : "lg:left-16",
        )}
      >
        <button
          aria-label="Buka navigasi"
          onClick={() => setOpen(!open)}
          className="flex h-12 w-12 items-center justify-center text-lg text-white hover:bg-[#e08e0b] lg:hidden"
        >
          &#9776;
        </button>
        <span className="hidden px-4 text-sm font-semibold text-white lg:inline">
          Intelligent Compliance Engine
        </span>
        <span className="flex items-center gap-2 text-sm font-semibold text-white">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/25 text-xs font-bold">
            V
          </span>
          Verifikator
        </span>
      </header>

      {/* Overlay mobile */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar gelap — hover untuk melebar (desktop) */}
      <aside
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className={cn(
          "group fixed inset-y-0 left-0 z-50 flex flex-col overflow-hidden bg-[#222d32] transition-all duration-200 lg:translate-x-0",
          // mobile: drawer geser, lebar penuh 56
          open ? "translate-x-0 w-56" : "-translate-x-full w-56",
          // desktop: selalu tampil, lebar mengikuti hover
          expanded ? "lg:w-56" : "lg:w-16",
        )}
      >
        <div className="flex h-12 shrink-0 items-center bg-white px-3">
          <Logo showText={expanded} />
        </div>
        <p
          className={cn(
            "bg-[#1a2226] px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-[#4b646f] transition-opacity",
            expanded ? "opacity-100" : "lg:opacity-0",
          )}
        >
          Navigasi
        </p>
        <nav className="flex-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              title={l.label}
              className={cn(
                "flex items-center gap-3 border-l-4 px-4 py-2.5 text-sm transition",
                pathname === l.href
                  ? "border-[#f39c12] bg-[#1e282c] font-semibold text-white"
                  : "border-transparent text-[#b8c7ce] hover:bg-[#1e282c] hover:text-white",
              )}
            >
              <span aria-hidden className="w-4 shrink-0 text-center">{l.icon}</span>
              <span className={cn("whitespace-nowrap", expanded ? "inline" : "lg:hidden")}>
                {l.label}
              </span>
            </Link>
          ))}
        </nav>
        <button
          onClick={handleLogout}
          title="Sign Out"
          className="flex items-center gap-3 border-l-4 border-transparent px-4 py-3 text-left text-sm text-[#b8c7ce] hover:bg-[#1e282c] hover:text-white"
        >
          <span aria-hidden className="w-4 shrink-0 text-center">&#10162;</span>
          <span className={cn("whitespace-nowrap", expanded ? "inline" : "lg:hidden")}>
            Sign Out
          </span>
        </button>
      </aside>
    </>
  );
}