"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Logo } from "@/components/Logo";

export default function LoginPage() {
  const { login, isAuthenticated, ready } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && isAuthenticated) router.replace("/dashboard");
  }, [ready, isAuthenticated, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login gagal.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#22272e] px-4 py-10">
      <div aria-hidden className="pointer-events-none absolute -top-32 right-[-10%] h-[30rem] w-[30rem] rounded-full bg-white/5 blur-3xl" />
      <div className="w-full max-w-md space-y-3">
        <details className="group bg-white shadow-sm">
          <summary className="flex cursor-pointer list-none items-center justify-between border-t-4 border-[#f39c12] px-4 py-3 text-sm font-semibold text-slate-700">
            PANDUAN LOGIN APLIKASI
            <span aria-hidden className="text-slate-400 group-open:rotate-45 transition">+</span>
          </summary>
          <div className="border-t border-slate-200 px-4 py-3 text-sm text-slate-600">
            Gunakan akun verifikator yang diberikan admin. Setelah masuk, unggah berkas
            sertifikat melalui menu Unggah Batch dengan format nama{" "}
            <code className="rounded bg-slate-100 px-1">nomorujian-urutan.ext</code>.
          </div>
        </details>
        <details className="group bg-white shadow-sm">
          <summary className="flex cursor-pointer list-none items-center justify-between border-t-4 border-[#f39c12] px-4 py-3 text-sm font-semibold text-slate-700">
            JADWAL KEGIATAN
            <span aria-hidden className="text-slate-400 group-open:rotate-45 transition">+</span>
          </summary>
          <div className="border-t border-slate-200 px-4 py-3 text-sm text-slate-600">
            Periode verifikasi sertifikat prestasi SNBP berlangsung sesuai kalender
            admisi POLBAN tahun berjalan.
          </div>
        </details>

        <div className="border-t-4 border-[#f39c12] bg-white px-8 py-8 shadow-xl">
          <div className="mb-1 flex justify-center">
            <Logo />
          </div>
          <p className="mb-6 text-center text-sm text-slate-600">
            Verifikator - Sign in to start your session
          </p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="relative">
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
                autoComplete="username"
                className="pr-10"
                required
              />
              <span aria-hidden className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">
                &#9993;
              </span>
            </div>
            <div className="relative">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                autoComplete="current-password"
                className="pr-10"
                required
              />
              <span aria-hidden className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">
                &#128274;
              </span>
            </div>
            {error && (
              <p className="rounded-[3px] bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
            )}
            <div className="flex items-center justify-between pt-1">
              <span className="text-sm text-[#3c8dbc]" title="Hubungi admin untuk reset kata sandi">
                I forgot my password
              </span>
              <Button type="submit" loading={loading} className="px-6">
                Sign In
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
