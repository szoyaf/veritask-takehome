# Ground truth ekstraksi

18 pasal yang dicek manual, dipakai `eval/evaluate_extraction.py` untuk mengukur CER, akurasi struktur, dan pasal yang
hilang atau terduplikasi. Hasilnya ada di `eval/results/extraction_metrics.md`.

## Isi
| Peraturan | Jumlah | Pasal | Sumber teks GT |
|---|---|---|---|
| UU 11/2008 | 7 | 5, 12, 14, 27, 28, 29, 31 | Lapisan teks digital asli (PDF dari Word, bukan scan), jadi sama dengan teks resmi |
| UU 19/2016 | 4 | 26, 40, 45A, 45B | Ditranskripsi dari **gambar halaman** PDF, bukan dari lapisan teks OCR |
| UU 1/2024 | 7 | 13A, 16B, 17, 27, 27A, 27B, 40A | Ditranskripsi dari **gambar halaman** PDF, bukan dari lapisan teks OCR |

Pasal dipilih supaya mencakup pasal dengan ayat, huruf, dan angka, pasal sisipan (13A, 16B, 27A, 27B, 40A, 45A, 45B),
dan pasal yang judulnya rusak kena OCR (16B terbaca "168").

Untuk UU hasil scan, lapisan teksnya sendiri adalah OCR yang salah baca. Karena itu GT diambil dari gambar halaman.
Kalau diambil dari teks yang dibaca pipeline, kesalahan OCR-nya ikut masuk ke GT dan CER-nya jadi tidak bermakna.

## Format file `pasal/<peraturan>__<butir>__<pasal>.txt`
```
# peraturan: uu-2024-1
# butir: 6                 nomor butir di Pasal I UU perubahan; '-' untuk UU induk
# pasal: 17
# induk: -                 BAB/Bagian tempat pasal berada (hanya UU induk)
# halaman: 6
# verified: yes            evaluasi hanya memakai file dengan 'yes'
# sumber_gt: ditranskripsi dari gambar halaman PDF ...
(1) Penyelenggaraan Transaksi Elektronik dapat dilakukan dalam lingkup publik atau privat.
(2) ...
  a. ...                   huruf di dalam ayat: indentasi 2 spasi
    1. ...                 angka di dalam huruf: indentasi 4 spasi
```
Satu baris per ayat, huruf, atau angka. Ejaannya persis seperti dokumen resmi, termasuk huruf kapital. Tanpa nomor
halaman, kop, atau kata sambung akhir halaman. Tanda hubung asli dipertahankan (`Undang-Undang`).

## Inventaris pasal
`pasal_inventory.json` berisi daftar semua pasal yang harus ada: UU 2008 Pasal 1–54, dan untuk UU perubahan, pasal yang
teksnya dimuat di tiap butir (format `butir:pasal`). Daftar ini dipakai untuk menghitung pasal yang hilang, ekstra,
atau terduplikasi.

## Keterbatasan
Teks GT untuk UU hasil scan diketik ulang secara manual dari gambar halaman dan dicek kembali terhadap PDF. Belum ada
pengecekan ulang huruf per huruf oleh orang kedua.
