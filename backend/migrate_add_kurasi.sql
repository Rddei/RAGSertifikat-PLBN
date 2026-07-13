-- Migrasi: tambah 4 kolom kurasi SIMT ke tabel applicants (Postgres)
-- Aman dijalankan berulang kali (IF NOT EXISTS). Data lama tidak hilang.
--
-- Jalankan (contoh, sesuaikan kredensial/nama container):
--   docker compose exec -T db psql -U admin -d compliance_db < migrate_add_kurasi.sql
-- atau:
--   psql "$DATABASE_URL" -f migrate_add_kurasi.sql

ALTER TABLE applicants
  ADD COLUMN IF NOT EXISTS kurasi_status              VARCHAR,
  ADD COLUMN IF NOT EXISTS kurasi_skor_nama           DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS kurasi_skor_penyelenggara  DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS kurasi_ajang_terdekat      VARCHAR;
