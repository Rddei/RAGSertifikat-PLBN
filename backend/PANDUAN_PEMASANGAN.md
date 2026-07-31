# Paket Pembaruan — Alur Input Berbasis Nama File + Kriteria Resmi Deterministik

Tanggal paket: 18 Juli 2026 (H-6 sidang). Timpa file berikut ke folder backend
(struktur path sama), lalu `pip install -r requirements.txt` (ada dependensi
baru: `openpyxl`). Migrasi kolom database berjalan OTOMATIS saat startup.

## File BARU
| File | Fungsi |
|---|---|
| `data/kriteria_prodi.json` | Data kriteria resmi 37 prodi (18 D3 + 19 D4), hasil pembersihan sheet "Data Lengkap Prodi SNBP 2026" |
| `services/kriteria_lokal.py` | Lookup deterministik relevansi: (prodi+jenjang, jenis lomba, tingkat) → tercantum / tidak_tercantum / ambigu |
| `services/pendaftar_service.py` | Parser nama file `<id>-<indeks>.<ext>` + impor master pendaftar CSV/XLSX |
| `api/routes/pendaftar.py` | Endpoint `POST /api/pendaftar/import` dan `GET /api/pendaftar` |

## File DIUBAH
| File | Perubahan inti |
|---|---|
| `api/routes/batch.py` | Mode utama: file-only. Parse id dari nama file → lookup master → tolak di awal bila "pendaftar tidak tersedia". Field form lama opsional & diabaikan (frontend lama tetap jalan) |
| `core/agent.py` | Stage 2.6 lookup kriteria; simpan `id_pendaftaran`, `tanggal_terbit`, `kriteria_relevansi` |
| `core/audit.py` | Hasil lookup kriteria = FAKTA relevansi (tercantum→terpenuhi, tidak→tidak_terpenuhi, ambigu→nilai dari RAG/tinjauan). RAG turun peran jadi konteks naratif. (Sudah termasuk revisi skor deterministik sebelumnya) |
| `core/vision.py` | `tanggal` dipecah: `tanggal_pelaksanaan` + `tanggal_terbit`; prioritas sumber `nama_penyelenggara` (badan → kop → blok ttd → label panitia); multi-instansi ditulis dipisah koma |
| `services/kurasi_lokal.py` | Penyelenggara multi-instansi dipecah per kandidat, skor = maksimum (Pemkab+KONI+federasi tidak lagi merusak skor); stopwords `panitia/pelaksana/...` |
| `repositories/chromadb_repo.py` | `temperature=0` pada LLM sintesis RAG (sumber vonis tidak stabil antar-run) |
| `models/database.py` | Tabel baru `pendaftar`; kolom baru `applicants`: `id_pendaftaran`, `tanggal_terbit`, `kriteria_relevansi` |
| `main.py` | Registrasi router pendaftar + auto-migrasi kolom (idempoten) |
| `requirements.txt` | + `openpyxl` |

## Urutan uji setelah pasang
1. Jalankan server → cek log: "Kriteria prodi dimuat: 37 entri".
2. `POST /api/pendaftar/import` dengan CSV/XLSX master (kolom mengandung
   kata: id / nama / jurusan). Cek `GET /api/pendaftar`.
3. Ganti nama 3–5 file sampel ke format `<id>-<n>.pdf`, unggah via batch.
   Pastikan: file tanpa id valid muncul di `rejected` dengan alasan jelas.
4. Regenerasi kasus Keyla: harapan status **Ditolak**, reasoning menyebut
   hasil lookup resmi ("tidak tercantum ... item terdekat ...").
5. Baru jalankan run besar 160 file.

## Catatan frontend (opsional, boleh belakangan)
Halaman batch tidak lagi membutuhkan input nama/jurusan — backend
mengabaikannya. UI cukup disederhanakan menjadi drop file saja + tampilkan
daftar `rejected` dari respons.

## Untuk laporan (BAB IV)
Keputusan desain yang lahir dari paket ini: (1) arsitektur hybrid —
kriteria terstruktur via lookup deterministik, RAG untuk ketentuan naratif;
(2) validasi identitas di gerbang (tolak dini "pendaftar tidak tersedia");
(3) pemisahan tanggal pelaksanaan vs terbit; (4) semantik multi-penyelenggara
"minimal satu instansi terdaftar". Bobot skor & threshold dapat dikonfigurasi
via env: `BOBOT_NAMA/BOBOT_RELEVANSI/BOBOT_FRAUD`, `KRITERIA_NAME_THRESHOLD`,
`KRITERIA_JSON_PATH`.
