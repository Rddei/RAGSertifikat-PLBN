import { Badge } from "@/components/ui/Badge";

// Data flag SIMT bisa datang dari VerifyResponse.flags (key lengkap) atau
// langsung dari objek Applicant (kolom tersimpan). Keduanya didukung.
export interface SimtFlagData {
  nama_terdaftar_simt?: boolean | null;
  tingkat_keyakinan_simt?: string | null;
  penyelenggara_terkurasi?: boolean | null;
}

function KeyakinanBadge({ tingkat }: { tingkat?: string | null }) {
  switch (tingkat) {
    case "tinggi":
      return <Badge color="green">✅ Identitas terverifikasi (NISN)</Badge>;
    case "sedang":
      return <Badge color="amber">🟡 Nama cocok (perlu konfirmasi)</Badge>;
    case "rendah":
      return <Badge color="red">🔴 Ambigu — cek manual</Badge>;
    case "tidak_ditemukan":
      return <Badge color="slate">Tidak terdaftar di SIMT</Badge>;
    default:
      return <Badge color="slate">Belum terverifikasi</Badge>;
  }
}

function PenyelenggaraBadge({ terkurasi }: { terkurasi?: boolean | null }) {
  if (terkurasi === true)
    return <Badge color="green">Penyelenggara terkurasi</Badge>;
  if (terkurasi === false)
    return <Badge color="amber">Penyelenggara tidak terkurasi</Badge>;
  return <Badge color="slate">Penyelenggara belum dicek</Badge>;
}

/**
 * Menampilkan flag SIMT PUSPRESNAS.
 * - compact: hanya badge tingkat keyakinan (untuk baris tabel).
 * - default: kartu lengkap dengan keterangan bahwa ini bukan bagian skor.
 */
export function SimtFlags({
  flags,
  compact = false,
}: {
  flags: SimtFlagData;
  compact?: boolean;
}) {
  if (compact) {
    return <KeyakinanBadge tingkat={flags.tingkat_keyakinan_simt} />;
  }

  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-sm font-medium text-slate-700">Flag SIMT PUSPRESNAS</p>
      <p className="mb-2 text-xs text-slate-400">
        Informasi tambahan — tidak memengaruhi skor kepatuhan.
      </p>
      <div className="flex flex-wrap gap-2">
        <KeyakinanBadge tingkat={flags.tingkat_keyakinan_simt} />
        <PenyelenggaraBadge terkurasi={flags.penyelenggara_terkurasi} />
      </div>
    </div>
  );
}
