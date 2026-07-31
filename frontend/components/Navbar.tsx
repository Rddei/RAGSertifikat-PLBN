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
  { href: "/upload", label: "Verifikasi Satuan", icon: "\u2714" },
  { href: "/kb-editor", label: "Basis Pengetahuan", icon: "\u270E" },
];

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <>
      {/* Topbar oranye */}
      <header className="fixed top-0 right-0 left-0 z-40 flex h-12 items-center justify-between bg-[#f39c12] pr-4 lg:left-56">
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

      {/* Sidebar gelap */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-56 flex-col bg-[#222d32] transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-12 items-center bg-white px-3">
          <Logo />
        </div>
        <p className="bg-[#1a2226] px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-[#4b646f]">
          Navigasi
        </p>
        <nav className="flex-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 border-l-4 px-4 py-2.5 text-sm transition",
                pathname === l.href
                  ? "border-[#f39c12] bg-[#1e282c] font-semibold text-white"
                  : "border-transparent text-[#b8c7ce] hover:bg-[#1e282c] hover:text-white",
              )}
            >
              <span aria-hidden className="w-4 text-center">{l.icon}</span>
              {l.label}
              <span className="ml-auto text-xs text-[#4b646f]">&#8250;</span>
            </Link>
          ))}
        </nav>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 border-l-4 border-transparent px-4 py-3 text-left text-sm text-[#b8c7ce] hover:bg-[#1e282c] hover:text-white"
        >
          <span aria-hidden className="w-4 text-center">&#10162;</span>
          Sign Out
        </button>
      </aside>
    </>
  );
}
