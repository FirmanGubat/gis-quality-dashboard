# 🗺️ GIS Quality Dashboard

Platform pengecekan kualitas data geospasial berbasis Streamlit.

## Fitur

| Fitur | Deskripsi |
|---|---|
| 🔐 Login via Spreadsheet | Autentikasi user dari Google Sheets publik |
| 🔬 Topology Check | Cek kualitas data GeoServer / ArcGIS |
| 📊 Scoring Kualitas Data | Lihat & filter scoring dari Metabase |
| 📄 Laporan PDF | Generate laporan otomatis dari template DOCX |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Konfigurasi Secrets

Edit `.streamlit/secrets.toml`:

```toml
[gsheets]
spreadsheet_url = "https://docs.google.com/spreadsheets/d/YOUR_ID/export?format=csv"

[geoserver]
username = "admin"
password = "your_password"
url_rest = "http://your-geoserver.com/geoserver/rest"
url_app  = "http://your-geoserver.com/geoserver"

[arcgis]
url_portal = "https://your-arcgis.com/portal"
username   = "admin"
password   = "password"
url_rest   = "https://your-arcgis.com/arcgis/rest/services"

[db_gis]
host     = "localhost"
port     = "5432"
username = "postgres"
password = "password"
database = "gis_db"

[geonetwork]
url      = "http://your-geonetwork.com/geonetwork"
username = "admin"
password = "admin"

[metabase]
url_scoring = "https://metabase.ekosistemdata.id/api/public/card/1acbc4ea-1fb9-4840-8aa6-a3ed71725e78/query/json"
```

### 3. Setup Google Sheets (untuk Login)

Buat spreadsheet dengan kolom:
| username | password | role | nama | opd |
|---|---|---|---|---|
| admin | password123 | superadmin | Nama Admin | Diskominfo |
| user1 | pass456 | admin | Nama User | Dinas XYZ |

> **Catatan:** Password bisa disimpan sebagai plaintext atau SHA-256 hash.
> Publish spreadsheet: File → Share → Publish to web → CSV

### 4. Jalankan

```bash
streamlit run app.py
```

## Deploy ke Streamlit Cloud

1. Push repo ke GitHub
2. Buka [share.streamlit.io](https://share.streamlit.io)
3. Connect repo, set `app.py` sebagai entry point
4. Di **Settings → Secrets**, paste isi `.streamlit/secrets.toml`

## Struktur Project

```
gis_app/
├── app.py                          # Entry point
├── requirements.txt
├── .streamlit/
│   ├── config.toml                 # Tema & konfigurasi
│   └── secrets.toml                # Credentials (jangan di-commit!)
├── pages/
│   ├── topology_check.py           # Halaman topology check
│   └── scoring.py                  # Halaman scoring Metabase
├── utils/
│   ├── auth.py                     # Autentikasi Google Sheets
│   ├── config.py                   # Akses secrets terpusat
│   └── topology.py                 # Fungsi-fungsi GIS
└── data_template/
    └── template_form_kualitas_data.docx
```

## Topology Check — Alur Pengecekan

```
1. Pilih Mapset (dari Satu Peta / Metabase)
2. Pilih Metadata (dari GeoNetwork)
3. Pilih Engine (GeoServer / ArcGIS) + Layer + Kolom Duplikasi
4. Set Parameter (Kesesuaian Nama, Timeliness)
5. Klik "Mulai Cek"
   ├── Cek Nama Kolom (huruf kapital)
   ├── Completeness Commission (atribut NULL)
   ├── Completeness Omission (geometry NULL)
   ├── Duplikasi Data
   ├── Topologi (validity / point in Jabar)
   ├── Metadata scoring (GeoNetwork)
   └── KUGI compliance
6. Hitung Skor Akhir
7. Download Laporan (DOCX / PDF)
```

## Catatan

- Untuk fitur **Cek Point di Jawa Barat**, diperlukan koneksi ke database PostGIS.
- Untuk konversi ke **PDF**, server harus memiliki **LibreOffice** terinstall.
- Di Streamlit Cloud, PDF tidak tersedia — gunakan DOCX.
