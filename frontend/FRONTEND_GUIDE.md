# Frontend — POLBAN Intelligent Compliance Engine

Frontend Next.js (App Router) + TypeScript + Tailwind yang sudah terintegrasi penuh
dengan backend FastAPI ber-autentikasi JWT.

## Struktur baru

```
app/
  layout.tsx          # membungkus AuthProvider + ToastProvider
  page.tsx            # redirect: ke /dashboard (login) atau /login
  login/page.tsx      # halaman login
  dashboard/page.tsx  # metrics + tabel pendaftar + export CSV + override status
  upload/page.tsx     # verifikasi 1 dokumen + tampil hasil
  globals.css
components/
  Providers.tsx       # client wrapper untuk context
  Navbar.tsx          # navigasi + tombol keluar
  FileUpload.tsx      # drag & drop + validasi (tipe & ukuran 20MB)
  ComplianceResult.tsx
  MetricsCards.tsx
  ApplicantsTable.tsx # tabel + dropdown override status
  StatusBadge.tsx
  ui/                 # Button, Card, Badge, Input, Spinner, Toast
lib/
  api.ts              # API client typed + Bearer otomatis + auto-logout 401
  auth.tsx            # AuthProvider + useAuth (token di localStorage)
  token.ts            # baca/tulis/hapus token
  useRequireAuth.ts   # guard halaman terproteksi
  types.ts            # tipe sesuai kontrak backend
  utils.ts            # cn(), formatDate(), scoreColor()
```

## Cara pakai

1. Salin folder `app/`, `components/`, `lib/`, dan `.env.example` ke proyek frontend Anda.
2. Buat file `.env.local`:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```
3. Jalankan:
   ```bash
   npm install
   npm run dev
   ```
4. Buka http://localhost:3000 -> diarahkan ke /login.
   Login pakai ADMIN_USERNAME & ADMIN_PASSWORD yang Anda set di backend.

## File lama yang bisa dihapus/diganti

- `app/result/page.tsx`  -> tidak dipakai lagi (hasil tampil inline di /upload).
- `lib/api.ts` lama       -> diganti versi baru (typed + Bearer).
- `components/ErrorMessage.tsx`, `components/LoadingSpinner.tsx`,
  `components/ComplianceResult.tsx`, `components/FileUpload.tsx` lama
  -> diganti versi baru. Hapus yang lama agar tidak bentrok.

## Catatan integrasi penting

- Semua endpoint admin kini WAJIB token. Client otomatis melampirkan
  `Authorization: Bearer <token>` dan akan auto-logout saat 401.
- Pastikan `CORS_ORIGINS` di backend memuat origin frontend
  (mis. http://localhost:3000).
- Jika proyek memakai Tailwind v3 (bukan v4), sesuaikan baris import di
  `app/globals.css` (lihat komentar di file tersebut).
- Alias `@/*` mengikuti default create-next-app (tsconfig: paths `@/*` -> `./*`).
