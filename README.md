# Intelligent Compliance Engine

**Agentic-RAG untuk Verifikasi Sertifikat Prestasi dalam Aplikasi Admisi POLBAN**

Proyek Tugas Akhir ini mengembangkan *Intelligent Compliance Engine*, sebuah purwarupa aplikasi berbasis **Agentic Retrieval-Augmented Generation (Agentic-RAG)** yang dirancang untuk membantu Unit Admisi Politeknik Negeri Bandung (POLBAN) dalam memverifikasi keabsahan sertifikat prestasi secara otomatis pada jalur seleksi mahasiswa baru (SNBP). Sistem mengekstraksi data esensial dari citra sertifikat, memvalidasinya terhadap pedoman resmi, dan menghasilkan **Compliance Score** beserta **reasoning** yang transparan dan dapat diaudit.

---

## Daftar Isi

- [Intelligent Compliance Engine](#intelligent-compliance-engine)
  - [Daftar Isi](#daftar-isi)
  - [Tentang Proyek](#tentang-proyek)
  - [Fitur Utama](#fitur-utama)
  - [Arsitektur Sistem](#arsitektur-sistem)
  - [Teknologi yang Digunakan](#teknologi-yang-digunakan)
  - [Struktur Proyek](#struktur-proyek)
  - [Prasyarat](#prasyarat)
  - [Instalasi dan Menjalankan Aplikasi](#instalasi-dan-menjalankan-aplikasi)
    - [1. Clone Repository](#1-clone-repository)
    - [2. Setup Backend](#2-setup-backend)
    - [3. Setup Knowledge Base](#3-setup-knowledge-base)
    - [4. Setup Frontend](#4-setup-frontend)
    - [5. Menjalankan Aplikasi](#5-menjalankan-aplikasi)
  - [Penggunaan](#penggunaan)
  - [Pengujian](#pengujian)
  - [Tim Pengembang](#tim-pengembang)
  - [Lisensi](#lisensi)

---

## Tentang Proyek

Proses verifikasi sertifikat prestasi calon mahasiswa baru di POLBAN selama ini dilakukan secara manual oleh tim verifikator. Kendala seperti variasi format sertifikat, hierarki level kompetisi (sekolah hingga internasional), serta kebutuhan validasi legalitas penyelenggara di Pusat Prestasi Nasional (PUSPRESNAS) menuntut adanya alat bantu otomatis yang andal.

*Intelligent Compliance Engine* hadir sebagai solusi inovatif yang memanfaatkan pendekatan **Agentic-RAG**. Arsitektur ini menggabungkan kemampuan penalaran otonom agen AI dengan pencarian informasi berbasis semantik dari *knowledge base* (Buku Pedoman Penerimaan Mahasiswa Baru POLBAN). Aplikasi dapat:

- Mengekstrak informasi penting dari citra sertifikat (nama peserta, penyelenggara, level, tanggal) menggunakan **LLM multimodal**.
- Mencari aturan relevan dari pedoman admisi melalui **vector database (ChromaDB)**.
- Memverifikasi silang legalitas penyelenggara ke basis data PUSPRESNAS sebagai *tool* eksternal.
- Memberikan **Compliance Score** dan **reasoning** yang merujuk langsung pada pasal-pasal aturan resmi.

Tugas Akhir ini disusun untuk memenuhi syarat kelulusan Program Sarjana Terapan Teknik Informatika di Jurusan Teknik Komputer dan Informatika, Politeknik Negeri Bandung.

---

## Fitur Utama

| Fitur | Keterangan |
|:---|:---|
| **Unggah Sertifikat** | Mendukung format JPG, PNG, PDF, WEBP dengan batas ukuran maksimum 20MB. |
| **Ekstraksi Data Esensial** | Menggunakan Google Gemini (LLM Multimodal) untuk membaca dan mengekstrak nama peserta, penyelenggara, judul kompetisi, level, peringkat, dan tanggal. |
| **Pencarian Aturan Semantik** | Mencari pasal-pasal relevan dari Buku Pedoman Admisi POLBAN yang telah diindeks dalam ChromaDB. |
| **Validasi Silang PUSPRESNAS** | Agen AI secara mandiri memanggil *tool* untuk memverifikasi legalitas penyelenggara. |
| **Compliance Score & Reasoning** | Menampilkan skor kepatuhan dalam bentuk persentase serta penjelasan logis yang merujuk langsung ke sumber aturan. |
| **Antarmuka Web Interaktif** | Dibangun dengan Next.js dan Tailwind CSS, mudah digunakan oleh verifikator. |

---

## Arsitektur Sistem

Aplikasi mengadopsi arsitektur modular dengan pemisahan tiga komponen utama yang berkomunikasi melalui RESTful API:

1. **Frontend** : Next.js + Tailwind CSS
2. **Backend** : FastAPI + LlamaIndex + Google Gemini
3. **Knowledge Base** : ChromaDB (vector database)

Di dalam modul backend, diterapkan **Layered Architecture** (Presentation, Business Logic, AI Orchestration, Data Access) serta siklus **Agentic-RAG** yang terdiri dari tiga tahap kognitif: *Persepsi*, *Penalaran & Tindakan*, *Penyintesisan*.

---

## Teknologi yang Digunakan

| Komponen | Teknologi | Versi |
|:---|:---|:---|
| Bahasa Pemrograman | Python | 3.11 |
| Framework API | FastAPI | 0.110+ |
| Orkestrasi AI | LlamaIndex | 0.10+ |
| LLM Multimodal | Google Gemini (Flash) | 2.5 |
| Embedding Model | text-embedding-004 | – |
| Vector Database | ChromaDB | 0.4+ |
| Ekstraksi PDF | PyMuPDF (fitz) | 1.23+ |
| Validasi Data | Pydantic | 2+ |
| Frontend Framework | Next.js (App Router) | 14 |
| UI Library | React | 18 |
| Styling | Tailwind CSS | 3 |
| Version Control | Git & GitHub | – |
| IDE | Visual Studio Code | – |

---

## Struktur Proyek
intelligent-compliance-engine/
├── backend/
│ ├── api/ # Lapisan Presentasi (API Routes)
│ ├── services/ # Lapisan Logika Bisnis
│ ├── core/ # Lapisan Orkestrasi AI (Agent + RAG)
│ ├── repositories/ # Lapisan Akses Data (ChromaDB)
│ ├── models/ # Skema Pydantic
│ ├── knowledge_base/ # Proses chunking, embedding, indexing
│ ├── data/ # Dokumen pedoman POLBAN (PDF)
│ └── main.py # Entry point FastAPI
├── frontend/
│ ├── app/ # Halaman (Next.js App Router)
│ ├── components/ # Komponen React
│ └── public/ # Aset statis
├── docs/ # Dokumentasi tambahan (opsional)
├── README.md
└── .gitignore


---

## Prasyarat

- **Python 3.11** atau lebih tinggi
- **Node.js 18** atau lebih tinggi
- **npm** atau **yarn**
- **Google Gemini API Key** (dapat diperoleh di [Google AI Studio](https://aistudio.google.com/))

---

## Instalasi dan Menjalankan Aplikasi

### 1. Clone Repository

```bash
git clone https://github.com/Rddei/intelligent-compliance-engine.git
cd intelligent-compliance-engine

