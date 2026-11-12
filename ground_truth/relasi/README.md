# Ground truth relasi

`relasi_gt.csv` berisi 69 relasi hasil pipeline yang dicek manual terhadap PDF, dipakai `eval/evaluate_relations.py`
untuk menghitung presisi dan recall per jenis relasi. Hasilnya ada di `eval/results/relation_metrics.md`.

## Cakupan
Cakupan ditentukan **sebelum** melihat hasil pipeline (`eval/make_relation_gt.py`, `REF_SCOPE` dan `scope_of`), supaya
recall bermakna: semua relasi yang seharusnya ada di dalam cakupan dibaca langsung dari PDF.

| Cakupan | Isi yang dibaca di PDF |
|---|---|
| S1 | Semua butir Pasal I UU 19/2016 (8 butir) dan UU 1/2024 (18 butir), plus kalimat pembuka Pasal I |
| S2 | Pasal II UU 1/2024 |
| S3 | Bagian Mengingat ketiga UU |
| S4 | Seluruh teks Pasal 5, 31, 36, 43, 52 UU 2008 (versi asli) dan Pasal 45 versi UU 2024 |

## Kolom `label`
- `benar`: relasi, pasal target, dan ayat (`ayat_target`, `detail`) sesuai PDF.
- `salah`: ada yang tidak sesuai, termasuk salah sebagian (misalnya target benar tapi ayat salah). Alasannya di `catatan`.
- `terlewat`: relasi yang ada di teks tapi tidak ditemukan pipeline (baris tambahan).

Presisi = benar / (benar + salah). Recall = benar / (benar + terlewat). Rujukan rentang
"Pasal 27 sampai dengan Pasal 34" dihitung sebagai satu relasi.

## Definisi
- `merujuk`: penyebutan pasal lain ("sebagaimana dimaksud dalam Pasal X"), bukan "pada ayat (n)" di pasal yang sama.
- `mendelegasikan`: "diatur dengan/dalam Peraturan Pemerintah/…".
