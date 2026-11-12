Relasi di sheet: 69 | sudah dilabel: 69 | belum: 0

| Relasi | benar | salah | terlewat | Presisi | Recall |
|---|---|---|---|---|---|
| dasar_hukum | 4 | 2 | 0 | 66.7% | 100.0% |
| membatasi_keberlakuan | 13 | 0 | 0 | 100.0% | 100.0% |
| mendelegasikan | 1 | 1 | 0 | 50.0% | 100.0% |
| mengubah | 29 | 0 | 0 | 100.0% | 100.0% |
| menyisipkan | 9 | 0 | 0 | 100.0% | 100.0% |
| merujuk | 10 | 0 | 0 | 100.0% | 100.0% |
| **SEMUA** | 66 | 3 | 0 | 95.7% | 100.0% |

### Relasi salah / terlewat

| id | label | relasi | source → target | catatan |
|---|---|---|---|---|
| R054 | salah | dasar_hukum | uu-2016-19 → uud-1945 | Relasi ke UUD benar, tapi pasal_dirujuk salah: Pasal 28D ayat (1) hilang (OCR '2gD'). PDF: 5(1), 20, 25A, 28D(1), 28E(2), 28E(3), 28F, 28G(1), 28J(2), 33(2). |
| R057 | salah | dasar_hukum | uu-2024-1 → uud-1945 | Relasi ke UUD benar, tapi pasal_dirujuk salah: '1' dan '281' adalah OCR; 28E hilang. PDF: 5(1), 20, 28D(1), 28E, 28F, 28G(1), 28I, 28J. |
| R069 | salah | mendelegasikan | uu-2008-11#pasal-5@uu-2008-11 → delegasi:UU | False positive: 'sesuai dengan ketentuan yang diatur dalam Undang-Undang ini' merujuk ke UU itu sendiri, bukan delegasi ke peraturan pelaksana. |
