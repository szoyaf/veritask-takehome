Ground truth files used: 18 (unverified remaining: 0)

| Metode | Pasal ditemukan | CER (ditemukan) | CER (incl. hilang=1) | Struktur P | Struktur R | Induk benar |
|---|---|---|---|---|---|---|
| pdfplumber | 18/18 | 0.44% | 0.44% | 97.53% | 96.34% | 100% |
| pymupdf | 12/18 | 0.11% | 33.41% | 100.00% | 64.63% | 100% |

### Inventaris pasal (hilang / ekstra / duplikat)
- pdfplumber · uu-2008-11 (inventaris belum diverifikasi): 54/54 ditemukan; hilang=-; ekstra=-; duplikat=-
- pdfplumber · uu-2016-19 (inventaris belum diverifikasi): 8/8 ditemukan; hilang=-; ekstra=-; duplikat=-
- pdfplumber · uu-2024-1 (inventaris belum diverifikasi): 19/19 ditemukan; hilang=-; ekstra=-; duplikat=-
- pymupdf · uu-2008-11 (inventaris belum diverifikasi): 54/54 ditemukan; hilang=-; ekstra=-; duplikat=-
- pymupdf · uu-2016-19 (inventaris belum diverifikasi): 8/8 ditemukan; hilang=-; ekstra=-; duplikat=-
- pymupdf · uu-2024-1 (inventaris belum diverifikasi): 3/19 ditemukan; hilang=['10:28', '11:29', '12:36', '13:40', '14:40A', '15:43', '16:45', '17:45A', '18:45B', '5:16A', '5:16B', '6:17', '7:18A', '8:27', '9:27A', '9:27B']; ekstra=-; duplikat=-

### Per pasal

**pdfplumber**

| GT file | CER | unit benar | catatan |
|---|---|---|---|
| uu-2008-11__-__12.txt | 0.00% | 9/9 |  |
| uu-2008-11__-__14.txt | 0.00% | 3/3 |  |
| uu-2008-11__-__27.txt | 0.00% | 4/4 |  |
| uu-2008-11__-__28.txt | 0.00% | 2/2 |  |
| uu-2008-11__-__29.txt | 0.00% | 0/0 |  |
| uu-2008-11__-__31.txt | 0.00% | 4/4 |  |
| uu-2008-11__-__5.txt | 0.00% | 6/6 |  |
| uu-2016-19__3__26.txt | 0.10% | 5/5 | insert: GT «…) Ketentuan mengenai tata[] cara penghapusan Informa…» vs PRED «[.]» |
| uu-2016-19__6__40.txt | 0.38% | 8/8 | replace: GT «…am melakukan pencegahan s[eb]agaimana dimaksud pada ay…» vs PRED «[6l]»; insert: GT «… institusi yang memiliki []data elektronik strategis…» vs PRED «[. ]» |
| uu-2016-19__8__45A.txt | 0.67% | 2/2 | insert: GT «…au denda paling banyak Rp[]1.000.000.000,00 (satu mi…» vs PRED «[ ]»; insert: GT «…da paling banyak Rp1.000.[]000.000,00 (satu miliar r…» vs PRED «[ ]» |
| uu-2016-19__8__45B.txt | 0.00% | 0/0 |  |
| uu-2024-1__14__40A.txt | 0.52% | 10/10 | replace: GT «…ka melaksanakan tanggung [j]awab sebagaimana dimaksud…» vs PRED «[J]»; replace: GT «…istratif sebagaimana dima[k]sud pada ayat (4) dapat b…» vs PRED «[l]» |
| uu-2024-1__3__13A.txt | 0.20% | 10/10 | replace: GT «…ayanan sebagaimana dimaks[u]d pada ayat (1) diatur da…» vs PRED «[q]» |
| uu-2024-1__5__16B.txt | 0.24% | 7/7 | delete: GT «…eguran tertulis; b. denda[ ]administratif; c. penghen…» vs PRED «[]» |
| uu-2024-1__6__17.txt | 5.30% | 3/4 | replace: GT «…ng diamankan dengan Serti[f]ikat Elektronik. (3) Kete…» vs PRED «[l]»; replace: GT «…an lebih lanjut mengenai [p]enyelenggaraan Transaksi …» vs PRED «[Transaksi ir]» |
| uu-2024-1__8__27.txt | 0.00% | 2/2 |  |
| uu-2024-1__9__27A.txt | 0.00% | 0/0 |  |
| uu-2024-1__9__27B.txt | 0.43% | 4/6 | delete: GT «… milik orang lain; atau b[.] memberi utang, membuat p…» vs PRED «[]»; replace: GT «…elawan hukum, dengan anca[m]an pencemaran atau dengan…» vs PRED «[rn]» |

**pymupdf**

| GT file | CER | unit benar | catatan |
|---|---|---|---|
| uu-2008-11__-__12.txt | 0.00% | 9/9 |  |
| uu-2008-11__-__14.txt | 0.00% | 3/3 |  |
| uu-2008-11__-__27.txt | 0.00% | 4/4 |  |
| uu-2008-11__-__28.txt | 0.00% | 2/2 |  |
| uu-2008-11__-__29.txt | 0.00% | 0/0 |  |
| uu-2008-11__-__31.txt | 0.00% | 4/4 |  |
| uu-2008-11__-__5.txt | 0.00% | 6/6 |  |
| uu-2016-19__3__26.txt | 0.10% | 5/5 | insert: GT «…) Ketentuan mengenai tata[] cara penghapusan Informa…» vs PRED «[.]» |
| uu-2016-19__6__40.txt | 0.38% | 8/8 | replace: GT «…am melakukan pencegahan s[eb]agaimana dimaksud pada ay…» vs PRED «[6l]»; insert: GT «… institusi yang memiliki []data elektronik strategis…» vs PRED «[. ]» |
| uu-2016-19__8__45A.txt | 0.67% | 2/2 | insert: GT «…au denda paling banyak Rp[]1.000.000.000,00 (satu mi…» vs PRED «[ ]»; insert: GT «…da paling banyak Rp1.000.[]000.000,00 (satu miliar r…» vs PRED «[ ]» |
| uu-2016-19__8__45B.txt | 0.00% | 0/0 |  |
| uu-2024-1__14__40A.txt | 100.00% | 0/10 | TIDAK DITEMUKAN |
| uu-2024-1__3__13A.txt | 0.20% | 10/10 | replace: GT «…ayanan sebagaimana dimaks[u]d pada ayat (1) diatur da…» vs PRED «[q]» |
| uu-2024-1__5__16B.txt | 100.00% | 0/7 | TIDAK DITEMUKAN |
| uu-2024-1__6__17.txt | 100.00% | 0/4 | TIDAK DITEMUKAN |
| uu-2024-1__8__27.txt | 100.00% | 0/2 | TIDAK DITEMUKAN |
| uu-2024-1__9__27A.txt | 100.00% | 0/0 | TIDAK DITEMUKAN |
| uu-2024-1__9__27B.txt | 100.00% | 0/6 | TIDAK DITEMUKAN |
