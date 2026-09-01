# Dashboard Monitoring Realisasi Penerimaan Pajak

Dashboard untuk memantau realisasi PKB, BBN, dan opsen berdasarkan periode cetak SKPD serta lokasi bayar. Data dimasukkan dengan upload CSV dan disimpan pada MySQL lokal.

## Persiapan awal

1. Buat virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Instal dependensi:

   ```powershell
   pip install -r requirements.txt
   ```

3. Salin konfigurasi database lokal:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Pastikan MySQL XAMPP aktif, lalu jalankan aplikasi:

   ```powershell
   streamlit run app.py
   ```

## Alur data

```text
CSV realisasi → Upload dashboard → MySQL lokal → Dashboard
```

Setiap upload memvalidasi CSV lalu mengganti snapshot cache pada tabel `dashboard_pajak.realisasi_pajak_cache`. Semua kolom dari CSV disimpan di cache lokal; aplikasi hanya menambahkan kolom perhitungan dashboard. Filter dan tampilan selalu membaca cache lokal.

## Database lokal

Atur `LOCAL_DATABASE_URL` di `.env` bila konfigurasi MySQL lokal Anda berbeda. Database `dashboard_pajak` akan dibuat otomatis saat upload pertama.

```env
LOCAL_DATABASE_URL=mysql+pymysql://root:@localhost:3306/dashboard_pajak
```

## Format CSV

Gunakan format ringkas pada `data/template_realisasi.csv`:

| Kolom | Keterangan |
| --- | --- |
| `periode` | Tanggal cetak SKPD, misalnya `2025-01-01` |
| `wilayah` | Lokasi/unit pembayaran |
| `realisasi_pkb` | Nominal PKB |
| `realisasi_bbn` | Nominal BBN |
| `opsen_pkb` | Nominal opsen PKB |
| `opsen_bbn` | Nominal opsen BBN |

Ekspor CSV dari query penetapan yang Anda kirim juga dapat digunakan langsung bila memuat `TglCetakSKPD`, `Lokasi_Bayar`, serta kolom-kolom nominal PKB/BBN/opsen. Seluruh kolom ekspor tersebut disimpan pada database lokal dan muncul pada tabel detail; aplikasi menghitung total setiap komponen otomatis.

## Kolom transaksi untuk Dashboard BI PKB & BBNKB

Untuk seluruh visual analitis (Januari--April 2026), gunakan ekspor transaksi yang
memuat kolom berikut. Nama variasi yang setara juga didukung oleh dashboard.

| Kebutuhan dashboard | Kolom yang diprioritaskan |
| --- | --- |
| Tanggal filter dan tren | `TglDaftar` (atau `TglCetakSKPD`) |
| Wilayah | `NamaWilayah`, `UPT`, atau `Lokasi_Bayar` |
| Volume transaksi | `Nopol` / `NoPol` |
| Komposisi kendaraan | `Jenis_Kendaraan`, `Merk`/`Merek`, `Model`/`Tipe` |
| Kepatuhan | `Jenis_Pendaftaran` |
| Denda | `DendaPKB`, `DendaBBN`, termasuk variasi tingkatannya |

Langkah penggunaan:

1. Jalankan MySQL XAMPP dan atur `LOCAL_DATABASE_URL` pada `.env`.
2. Jalankan `streamlit run app.py`.
3. Unggah CSV transaksi dan pilih **Simpan ke database lokal**. Progres penyimpanan
   tampil per 1.000 baris.
4. Gunakan filter global tanggal, wilayah/UPT, dan jenis kendaraan pada sidebar.

Jika kolom kendaraan atau pendaftaran belum tersedia, KPI dan chart berbasis
pendapatan tetap berfungsi; area analisis terkait menampilkan informasi kolom yang
perlu ditambahkan pada ekspor berikutnya.

## Struktur proyek

```text
app.py                  # Halaman utama Streamlit dan upload CSV
src/data_loader.py      # Validasi CSV dan cache MySQL lokal
data/template_realisasi.csv
.streamlit/config.toml  # Tema tampilan
```
