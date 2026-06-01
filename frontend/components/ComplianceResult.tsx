import { VerificationResult } from "@/lib/api";

export default function ComplianceResult({ data }: { data: VerificationResult }) {
  const isAccepted = data.audit.status.toLowerCase().includes("diterima");
  const isPending = data.audit.status.toLowerCase().includes("butuh tinjauan");

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4">
      <div className="text-center">
        <p className="text-3xl font-bold">
          <span className={isAccepted ? "text-green-600" : isPending ? "text-yellow-600" : "text-red-600"}>
            {data.audit.skor_kepatuhan}%
          </span>
        </p>
        <span
          className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
            isAccepted
              ? "bg-green-100 text-green-800"
              : isPending
              ? "bg-yellow-100 text-yellow-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          {data.audit.status}
        </span>
      </div>

      <div>
        <h3 className="font-semibold text-gray-700">Alasan</h3>
        <p className="text-gray-600 mt-1 text-sm">{data.audit.reasoning}</p>
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div><span className="font-medium">Nama:</span> {data.extraction.nama_peserta}</div>
        <div><span className="font-medium">Penyelenggara:</span> {data.extraction.nama_penyelenggara}</div>
        <div><span className="font-medium">Lomba:</span> {data.extraction.nama_lomba}</div>
        <div><span className="font-medium">Jenjang:</span> {data.extraction.jenjang_sekolah}</div>
      </div>

      {data.security.fraud_flags.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-800">
          ⚠️ Terdeteksi indikasi kecurangan: {data.security.fraud_flags.join(", ")}
        </div>
      )}
    </div>
  );
}