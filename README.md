# Ekstraksi Peraturan untuk RAG & Graph RAG — UU ITE

Pipeline kecil yang mengubah PDF UU 11/2008 (ITE), UU 19/2016 (Perubahan Pertama), dan UU 1/2024 (Perubahan Kedua)
menjadi teks per pasal berhierarki, metadata, graph relasi tingkat pasal dengan versi, dan chunk RAG.
Semua aturan deterministik (regex + pemeriksaan urutan), **tanpa LLM dan tanpa API berbayar** (biaya per 100 halaman: Rp0).

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python run.py --all-methods          # PDF → struktur → relasi/versi → metadata → chunk
.venv/Scripts/python eval/evaluate_extraction.py   # CER, akurasi struktur, pasal hilang/duplikat
.venv/Scripts/python eval/evaluate_relations.py    # presisi/recall relasi
.venv/Scripts/python eval/check_graph.py --pasal 27 --tanggal 2020-06-01   # validasi silang + rantai versi
.venv/Scripts/python eval/rag_examples.py          # 6 pertanyaan contoh → chunk
```
Output: `data/output/{structured,metadata,graph,chunks}/`. Sumber, tanggal unduh, dan sha256 tiap PDF: `data/sources.json`.

| Folder | Isi |
|---|---|
| `src/veritask/` | `extract` (PDF → teks) · `clean` (noise + koreksi OCR) · `parse` (hierarki) · `relations` + `graph` (relasi, versi, status) · `schema` + `metadata` · `chunks` · `pipeline` (urutan semua tahap) |
| `eval/` | skrip evaluasi; hasilnya di `eval/results/` |
| `ground_truth/` | 18 pasal GT, inventaris pasal, 69 relasi berlabel (cara pembuatannya di README masing-masing) |
| `data/raw/` · `data/output/` | PDF sumber · hasil pipeline (`data/interim/` = dump teks mentah/bersih per metode, tidak di-commit) |
| `docs/` | `catatan_teknis.md` (detail keputusan per bagian) · `script_presentasi.md` |

## Hasil (angka diukur terhadap ground truth manual)
| Ukuran | Hasil |
|---|---|
| Pasal terdeteksi vs inventaris (UU 2008 / 2016 / 2024) | 54/54 · 8/8 · 19/19, 0 duplikat (pdfplumber) |
| CER teks pasal, 18 pasal GT (pdfplumber) | **0,44%** (UU 2008 digital: 0,00% · scan 2016/2024: 0,10–5,30%, terburuk Pasal 17 UU 2024) |
| Akurasi struktur: unit ayat/huruf/angka dengan induk + teks benar | **P 97,5% · R 96,3%**; BAB/Bagian induk 100% (`eval/results/extraction_metrics.md`) |
| Presisi / recall relasi, 69 relasi di 4 cakupan tetap | **P 95,7% (66/69) · R 100% (0 terlewat)**; mengubah/menyisipkan/membatasi_keberlakuan/merujuk 100%, dasar_hukum 4/6, mendelegasikan 1/2 (`eval/results/relation_metrics.md`) |
| Validasi silang graph (target ubah ada, sisipan baru, rujukan ter-resolve, versi bersambung) | 0 masalah |
| Retrieval contoh (filter metadata + BM25) | 6/6 chunk yang diharapkan |

**Pemilihan metode ekstraksi.** pdfplumber vs PyMuPDF (keduanya membaca lapisan teks PDF). Pada UU 2024 PyMuPDF hanya
menghasilkan **3/19 pasal**: nomor butir perubahan ("8", "9") terlepas dari kalimatnya sehingga butir tak terdeteksi.
pdfplumber 19/19. Pada GT: PyMuPDF CER 33,4% bila pasal hilang dihitung 1, struktur R 64,6%; pdfplumber 0,44% / 96,3%.
Pada 12 pasal yang ditemukan keduanya CER sama (0,11%), karena sama-sama membaca lapisan OCR yang sama. Jadi bedanya ada di tata letak,
bukan pengenalan karakter. → **pdfplumber** dipilih. OCR ulang (Tesseract) sudah ada di kode tapi belum diukur.

## Keputusan desain
1. **Sumber ternyata scan.** UU 2008 dari BPK berupa teks digital; UU 2016 & 2024 berupa *scan* dengan OCR bawaan
   (terdeteksi dari cakupan gambar halaman 1.00 vs 0.01 → field `lapisan_teks`). Pembersih (`clean.py`) memperbaiki
   noise **hanya pada token struktural** (`(21`→`(2)`, `Pasal2TA`→`27A`, `l2l`→`(2)`), bukan prosa, supaya tidak merusak teks.
2. **Parser berbasis urutan.** Marker ayat/huruf/angka hanya diterima bila merupakan nomor *berikutnya yang diharapkan*
   (mendukung sisipan `2a`, `6a`, `7a`). Ini menolak "(1)" yang sebenarnya rujukan terbungkus baris.
   Judul pasal sisipan yang rusak OCR (`168`, `278`, `458`) dikoreksi dari instruksi butir
   ("di antara Pasal 16 dan 17 disisipkan 2 pasal" ⇒ 16A, 16B).
3. **UU 2008 sebagai UU terkonsolidasi.** `Pasal` (id stabil `uu-2008-11#pasal-27`) ≠ `PasalVersi`
   (`…#pasal-27@uu-2024-1`). Setiap butir perubahan membuat versi baru dan menutup versi lama
   (`berlaku_sampai`). Perubahan **penjelasan saja** juga membuat versi baru, karena tafsir resminya berubah.
4. **Status diturunkan, tidak diisi.** Status pasal/peraturan dihitung dari relasi per tanggal acuan (`--as-of`).
   Temuan penting: **Pasal II UU 1/2024** menyatakan Pasal 27(1), 27A, 28(2)(3), 36, 45(1)(2)(4)–(7), 45A(2)(3) berlaku
   *sampai KUHP (UU 1/2023) berlaku*, yaitu 2 Jan 2026. Ini dimodelkan sebagai relasi `membatasi_keberlakuan` di **tingkat ayat**:
   per hari ini Pasal 27A & 36 `tidak_berlaku`, Pasal 27/28/45/45A `berlaku_sebagian`.
5. **Relasi tingkat pasal dengan bukti.** Setiap edge menyimpan `kutipan`, lokasi (peraturan, butir, pasal, ayat, halaman),
   dan id `aturan` → bisa diaudit dan presisi bisa dihitung per aturan. `mengubah` mencatat ayat yang diubah/disisipkan.
6. **Chunk mengikuti unit hukum.** Satu chunk per versi pasal; dipecah per ayat bila > 512 token (batas umum model embedding
   multibahasa; estimasi konservatif 3,5 char/token) **atau bila ayatnya punya masa berlaku berbeda**, supaya filter bisa
   membuang tepat ayat yang sudah mati. Penjelasan = chunk terpisah yang ditautkan ("Cukup jelas." dibuang).
7. **Metadata dengan asal.** Setiap field di JSON Schema diberi `asal`: ekstraksi / turunan / model / sumber.
   `bidang` = klasifikator kata kunci (ditandai *model*). `pemrakarsa` sengaja `null` karena UU tidak menyebutnya.

## Trade-off
- Aturan > LLM: deterministik, gratis, mudah diaudit. Kelemahannya rapuh terhadap pola kalimat baru di peraturan lain.
- Koreksi OCR hanya untuk token struktural → struktur akurat, tetapi salah ketik di isi (`sEuna`, `dimaksqd`) tetap masuk ke CER.
- Estimasi token tanpa tokenizer nyata → aman (tidak terpotong), tetapi chunk sedikit lebih kecil dari batas sebenarnya.

## Kegagalan yang diketahui (contoh)
1. Mengingat UU 2024: nomor "1" OCR jatuh di tengah kalimat → 1 item terbaca, seharusnya 2; daftar pasal UUD salah (`281` = 28I).
2. Pasal 17(3) UU 2024: urutan kata rusak oleh layout OCR (CER 5,3%, tertinggi). Pasal 27B(1) UU 2024: OCR menghapus titik
   di "b." sehingga huruf b menempel ke huruf a → satu-satunya kesalahan struktur di GT.
3. `Pasal 278` dan `ayat (11)` di dalam rujukan (OCR 27B / (1)) awalnya membuat rujukan menggantung. **Ditangkap validasi
   silang**, lalu dikoreksi hanya bila target hasil koreksi benar-benar ada (nilai asli disimpan di `target_ocr`).
4. PyMuPDF kehilangan 16/19 pasal di UU 2024 (urutan baca butir).
5. Relasi salah (3/69): daftar pasal UUD di Mengingat rusak OCR (2×), dan "diatur dalam Undang-Undang ini" salah dibaca
   sebagai `mendelegasikan` (merujuk ke UU itu sendiri). Recall 100% hanya berlaku pada cakupan sampel 69 relasi; cakupan rujukan
   (S4) baru mencakup 6 pasal.
6. BM25 murni gagal untuk pertanyaan definisi (penjelasan panjang menang atas definisi satu baris) → router "yang dimaksud dengan".

## Asumsi (diambil tanpa bertanya)
- Tanggal berlaku KUHP (2026-01-02, Pasal 624 UU 1/2023) berada di luar korpus → diisi manual dengan sumber di
  `data/external_facts.json`, ditandai `manual_eksternal`. Status per tanggal acuan default = hari pipeline dijalankan.
- `berlaku_sampai` eksklusif: versi lama berakhir pada hari versi baru mulai berlaku.
- Rujukan "Pasal X" tanpa nama UU di dalam UU perubahan → pasal UU 2008 terkonsolidasi pada versi yang berlaku saat itu.

## Bila diberi 2 minggu lagi
1. OCR ulang halaman scan (Tesseract `ind` / PaddleOCR) + koreksi kata isi dengan kamus istilah hukum; ukur CER per metode.
2. Tambah KUHP (UU 1/2023 Pasal 622 mencabut sebagian pasal ITE) dan Putusan MK (`diuji_oleh`) ke graph.
3. Resolve `mendelegasikan` ke PP konkret (PP 71/2019 dst.) dan uji parser pada rantai lain (UU Ketenagakerjaan → Cipta Kerja).
4. Embedding + hybrid search, evaluasi retrieval dengan ±50 pertanyaan berlabel; versi konsolidasi otomatis per tanggal.
5. Evaluasi `bidang` terhadap label manual; perluas GT ke Penjelasan.
