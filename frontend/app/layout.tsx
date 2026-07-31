import type { Metadata } from "next";
import { Source_Sans_3 } from "next/font/google";

const jakarta = Source_Sans_3({ subsets: ["latin"], weight: ["400","600","700"] });
import "./globals.css";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: "POLBAN Compliance Engine",
  description: "Verifikasi sertifikat admisi POLBAN berbasis AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className={`${jakarta.className} min-h-screen bg-[#ecf0f5] text-slate-900 antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
