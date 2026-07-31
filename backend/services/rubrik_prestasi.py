"""
Penilaian POIN PRESTASI menurut rubrik resmi (sheet "Rubrik nilai"):

    Total = Poin Bidang + Poin Tingkat + Poin Individu/Kelompok
    Bidang : Olimpiade (semua cabang) = 10; Olahraga/Seni/Drama-Sastra/
             Pramuka-Ekskul/Penelitian = 5
    Tingkat: Internasional 20, Nasional 15, Provinsi 10, Kab/Kota 5
             (CATATAN: berbeda dari normalisasi KELAYAKAN -- di rubrik ini
             Provinsi adalah jenjang tersendiri, TIDAK disetarakan Kab/Kota.
             Tingkat "Lokal" tidak ada pada rubrik -> tidak ternilai.)
    Ind/Kel: Individu 20, Kelompok 10

Prinsip:
  - Murni deterministik (tanpa LLM); PISAH TOTAL dari skor kepatuhan --
    ini mengukur BOBOT prestasi, bukan lolos-tidaknya pemeriksaan.
  - Komponen yang tidak dapat ditentukan dari data ekstraksi TIDAK ditebak:
    nilainya None, tercatat di 'belum_ternilai', dan 'total' hanya diisi
    bila ketiga komponen lengkap ('total_parsial' selalu tersedia).
"""

import re

# --- Poin bidang -----------------------------------------------------------
_OLIMPIADE_CABANG = {
    "matematika": "Olimpiade Matematika",
    "fisika": "Olimpiade Fisika",
    "kimia": "Olimpiade Kimia",
    "biologi": "Olimpiade Biologi",
    "astronomi": "Olimpiade Astronomi & Astrofisika",
    "astrofisika": "Olimpiade Astronomi & Astrofisika",
    "komputer": "Olimpiade Komputer",
    "informatika": "Olimpiade Komputer",
    "geografi": "Olimpiade Geografi",
    "kebumian": "Olimpiade Ilmu Kebumian",
    "ekonomi": "Olimpiade Ekonomi",
}
_OLIMPIADE_MARKER = ("olimpiade", "olympiad", "osn", "ksn", "o2sn", "olimpiade sains")

_BIDANG_5 = [
    ("Olahraga", ("olahraga", "sepak", "futsal", "basket", "voli", "badminton",
                  "bulu tangkis", "bulutangkis", "silat", "pencak", "karate",
                  "taekwondo", "judo", "renang", "atletik", "lari", "catur",
                  "panahan", "archery", "tenis", "senam", "hoki", "hockey",
                  "tarung", "kumite", "kata ", "tanding", "pon", "porkab",
                  "porda", "porprov", "kejurda", "kejurnas", "kejurkab")),
    ("Seni Suara/Musik", ("paduan suara", "vokal", "menyanyi", "musik", "band",
                          "nasyid", "solo vocal", "choir", "folklore")),
    ("Seni Tari", ("tari", "dance")),
    ("Seni Rupa/Lukis", ("lukis", "melukis", "gambar", "rupa", "kaligrafi",
                         "desain grafis", "fotografi")),
    ("Drama/Sastra", ("drama", "teater", "puisi", "sastra", "cerpen", "pidato",
                      "debat", "story telling", "essay", "esai")),
    ("Pramuka/Organisasi Ekstrakurikuler", ("pramuka", "paskibra", "ekstrakurikuler",
                                            "osis", "pmr")),
    ("Penelitian", ("penelitian", "karya ilmiah", "riset", "kir", "lkir",
                    "science project", "inovasi")),
    # Fallback kelas seni generik: sertifikat yang hanya menulis "seni" tanpa
    # cabang spesifik tetap bernilai 5 (semua kelas seni bernilai sama).
    ("Seni (umum)", ("seni",)),
]

# --- Poin tingkat (rubrik; Provinsi BERDIRI SENDIRI) ------------------------
_TINGKAT_POIN = [
    (("internasional", "international"), ("Internasional", 20)),
    (("nasional", "national"), ("Nasional", 15)),
    (("provinsi", "propinsi", "se-provinsi", "se provinsi"), ("Provinsi", 10)),
    (("kabupaten", "kab/", "kab.", "kota", "kab-kota"), ("Kab/Kota", 5)),
]

# --- Individu / Kelompok ----------------------------------------------------
_KELOMPOK_KW = ("beregu", "regu", "tim ", " tim", "team", "kelompok", "ganda",
                "duet", "trio", "paduan suara", "ansambel", "ensemble", "grup",
                "group", "mixed team", "double", "estafet", "kontingen")
_INDIVIDU_KW = ("perorangan", "individu", "tunggal", "single", "solo",
                "tanding kelas", "kumite", "kata perorangan")

# Cabang yang SECARA HAKIKAT beregu -- tak perlu tertulis "beregu" di
# sertifikat. Daftar sengaja konservatif: hanya cabang yang tidak punya
# nomor perorangan (badminton/tenis/silat TIDAK masuk karena bernomor
# tunggal & ganda).
_CABANG_BEREGU = ("sepak bola", "sepakbola", "futsal", "basket", "voli",
                  "volley", "hoki", "hockey", "paduan suara", "choir",
                  "ansambel", "ensemble", "band", "teater", "drama",
                  "kabaret", "marching band", "folklore", "cheerleading")


def _lc(*parts: str) -> str:
    return " ".join((p or "") for p in parts).lower()


def hitung_skor_prestasi(kategori: str, nama_lomba: str, tingkat: str,
                         peringkat: str) -> dict:
    """Hitung poin rubrik resmi dari field hasil ekstraksi. Fail-safe: tidak
    pernah melempar; komponen tak terdeteksi bernilai None + tercatat."""
    hasil = {
        "bidang": None, "poin_bidang": None,
        "tingkat": None, "poin_tingkat": None,
        "partisipasi": None, "poin_partisipasi": None,
        "partisipasi_sumber": None,
        "total": None, "total_parsial": 0, "belum_ternilai": [],
    }
    try:
        teks = _lc(kategori, nama_lomba)

        # 1) Bidang -- cabang olimpiade dicek DULU (10), lalu penanda
        #    olimpiade umum (10), baru kelas bidang 5 poin.
        for kw, label in _OLIMPIADE_CABANG.items():
            if kw in teks and any(m in teks for m in _OLIMPIADE_MARKER):
                hasil["bidang"], hasil["poin_bidang"] = label, 10
                break
        if hasil["poin_bidang"] is None and any(m in teks for m in _OLIMPIADE_MARKER):
            # O2SN adalah olimpiade OLAHRAGA -> bidang Olahraga (5), bukan 10.
            if "o2sn" in teks or "olahraga" in teks:
                hasil["bidang"], hasil["poin_bidang"] = "Olahraga", 5
            else:
                hasil["bidang"], hasil["poin_bidang"] = "Olimpiade (Lainnya)", 10
        if hasil["poin_bidang"] is None:
            for label, kws in _BIDANG_5:
                if any(kw in teks for kw in kws):
                    hasil["bidang"], hasil["poin_bidang"] = label, 5
                    break
        if hasil["poin_bidang"] is None:
            hasil["belum_ternilai"].append("bidang")

        # 2) Tingkat -- normalisasi KHUSUS rubrik (Provinsi != Kab/Kota).
        t = _lc(tingkat)
        if t.strip():
            for kws, (label, poin) in _TINGKAT_POIN:
                if any(kw in t for kw in kws):
                    hasil["tingkat"], hasil["poin_tingkat"] = label, poin
                    break
        if hasil["poin_tingkat"] is None:
            hasil["belum_ternilai"].append(
                "tingkat (kosong/Lokal -- tidak ada pada rubrik)")

        # 3) Individu/Kelompok. Kebijakan (keputusan pemilik sistem):
        #    a. kata kunci kelompok eksplisit           -> Kelompok (eksplisit)
        #    b. kata kunci individu eksplisit           -> Individu (eksplisit)
        #    c. cabang yang hakikatnya beregu           -> Kelompok (cabang beregu)
        #    d. selain itu DEFAULT Individu -- karena Individu bernilai poin
        #       LEBIH TINGGI (20 vs 10), default ini bisa menggelembungkan
        #       skor; sumbernya dicatat agar verifikator tahu mana asumsi.
        tp = _lc(kategori, peringkat, nama_lomba)
        if any(kw in tp for kw in _KELOMPOK_KW):
            hasil["partisipasi"], hasil["poin_partisipasi"] = "Kelompok", 10
            hasil["partisipasi_sumber"] = "eksplisit"
        elif any(kw in tp for kw in _INDIVIDU_KW):
            hasil["partisipasi"], hasil["poin_partisipasi"] = "Individu", 20
            hasil["partisipasi_sumber"] = "eksplisit"
        elif any(kw in tp for kw in _CABANG_BEREGU):
            hasil["partisipasi"], hasil["poin_partisipasi"] = "Kelompok", 10
            hasil["partisipasi_sumber"] = "cabang beregu"
        else:
            hasil["partisipasi"], hasil["poin_partisipasi"] = "Individu", 20
            hasil["partisipasi_sumber"] = "default (tidak tertulis)"

        poin = [hasil["poin_bidang"], hasil["poin_tingkat"],
                hasil["poin_partisipasi"]]
        hasil["total_parsial"] = sum(p for p in poin if p is not None)
        if all(p is not None for p in poin):
            hasil["total"] = hasil["total_parsial"]
        return hasil
    except Exception:
        hasil["belum_ternilai"] = ["kesalahan internal penilaian"]
        return hasil
