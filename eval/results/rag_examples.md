# Contoh retrieval (tanggal acuan 2026-11-12; filter metadata + BM25, tanpa embedding)

**6/6 pertanyaan mengambil chunk yang diharapkan.**

## Q1. Apa bunyi Pasal 27 ayat (3) UU ITE yang berlaku saat ini?

- parse: {'pasal': '27', 'ayat': '3', 'tanggal': '2026-11-12'}
- diharapkan: TIDAK ADA chunk berlaku → fallback uu-2008-11#pasal-27@uu-2016-19::pasal
- ✅ terambil (top-3): —
- tidak ada versi berlaku pada 2026-11-12; versi terakhir yang memuatnya: `uu-2008-11#pasal-27@uu-2016-19::pasal` (berlaku 2016-11-25 s.d. 2024-01-02); versi pasal yang berlaku sekarang: ['uu-2008-11#pasal-27@uu-2024-1::ayat-2']
- catatan: Jebakan versi: sejak UU 1/2024 Pasal 27 hanya 2 ayat; muatan penghinaan pindah ke Pasal 27A, yang menurut Pasal II UU 1/2024 berakhir saat KUHP berlaku (2026-01-02). Jawaban benar: tidak ada lagi.

## Q2. Bagaimana bunyi Pasal 27 ayat (3) UU ITE pada tahun 2020?

- parse: {'pasal': '27', 'ayat': '3', 'tanggal': '2020-07-01'}
- diharapkan: ['uu-2008-11#pasal-27@uu-2016-19::pasal']
- ✅ terambil (top-3): ['uu-2008-11#pasal-27@uu-2016-19::pasal']
- top-1 header: `UU 11/2008 (ITE, diubah UU 1/2024) › BAB VII Perbuatan yang Dilarang › Pasal 27 [bunyi menurut UU 19/2016 · berlaku 2016-11-25 s.d. 2024-01-02]`
- top-1 teks: (1) Setiap Orang dengan sengaja dan tanpa hak mendistribusikan dan/atau mentransmisikan dan/atau membuat dapat diaksesnya Informasi Elektronik dan/atau Dokumen Elektronik yang memiliki muatan yang melanggar kesusilaan. (…
- penjelasan tertaut: `uu-2008-11#pasal-27@uu-2016-19::penjelasan`
- catatan: Versi 2016 (teks 2008, penjelasan diubah 2016); penjelasan tertaut: ::penjelasan

## Q3. Apa ancaman pidana bagi orang yang menyebarkan berita bohong yang mengakibatkan kerugian konsumen dalam Transaksi Elektronik?

- parse: {'pasal': None, 'ayat': None, 'tanggal': '2026-11-12'}
- diharapkan: ['uu-2008-11#pasal-45A@uu-2024-1::ayat-1', 'uu-2008-11#pasal-28@uu-2024-1::ayat-1']
- ✅ terambil (top-3): ['uu-2008-11#pasal-28@uu-2024-1::ayat-1', 'uu-2008-11#pasal-45A@uu-2024-1::ayat-1', 'uu-2008-11#pasal-3@uu-2008-11::penjelasan']
- top-1 header: `UU 11/2008 (ITE, diubah UU 1/2024) › BAB VII Perbuatan yang Dilarang › Pasal 28 ayat (1) [bunyi menurut UU 1/2024 · berlaku 2024-01-02 s.d. sekarang]`
- top-1 teks: (1) Setiap Orang dengan sengaja dan/atau mentransmisikan Informasi Elektronik dan/atau Dokumen Elektronik yang berisi pemberitahuan bohong atau informasi menyesatkan yang mengakibatkan kerugian materiel bagi konsumen dal…
- penjelasan tertaut: `uu-2008-11#pasal-28@uu-2024-1::penjelasan`
- catatan: 45A ayat (1) masih berlaku (Pasal II hanya membatasi ayat 2 dan 3)

## Q4. Apa kewajiban Penyelenggara Sistem Elektronik dalam memberikan pelindungan bagi anak?

- parse: {'pasal': None, 'ayat': None, 'tanggal': '2026-11-12'}
- diharapkan: ['uu-2008-11#pasal-16A@uu-2024-1::pasal']
- ✅ terambil (top-3): ['uu-2008-11#pasal-16A@uu-2024-1::pasal', 'uu-2008-11#pasal-16A@uu-2024-1::penjelasan', 'uu-2008-11#pasal-18A@uu-2024-1::penjelasan']
- top-1 header: `UU 11/2008 (ITE, diubah UU 1/2024) › BAB IV Penyelenggaraan Sertifikasi Elektronik dan Sistem Elektronik › Bagian Kedua Penyelenggaraan Sistem Elektronik › Pasal 16A [bunyi menurut UU 1/2024 · berlaku 2024-01-02 s.d. sekarang]`
- top-1 teks: (1) Penyelenggara Sistem Elektronik wajib memberikan pelindungan bagi anak yang menggunakan atau mengakses Sistem Elektronik. (2) Pelindungan sebagaimana dimaksud pada ayat (1) meliputi pelindungan terhadap hak anak seba…
- penjelasan tertaut: `uu-2008-11#pasal-16A@uu-2024-1::penjelasan`
- catatan: Pasal sisipan UU 1/2024

## Q5. Ketentuan mana dalam UU ITE yang berlaku sampai dengan diberlakukannya Kitab Undang-Undang Hukum Pidana?

- parse: {'pasal': None, 'ayat': None, 'tanggal': '2026-11-12'}
- diharapkan: ['uu-2024-1::pasal-II']
- ✅ terambil (top-3): ['uu-2024-1::pasal-II', 'uu-2008-11#pasal-42@uu-2008-11::pasal', 'uu-2008-11#pasal-52@uu-2008-11::pasal']
- top-1 header: `UU 1/2024 (Undang-Undang Nomor 1 Tahun 2024 tentang Perubahan Kedua atas Undang-Undang Nomor 11 Tahun 2008 tentang Informasi dan Transaksi Elektronik) › Pasal II (ketentuan keberlakuan)`
- top-1 teks: Pada saat Undang-Undang ini mulai berlaku, 1 ketentuan dalam Pasal 27 ayat (1), Pasal 27A, Pasal. 28 ayat (2), Pasal 28 ayat (3), Pasal 36, Pasal 45 ayat (1), Pasal 45 ayat (2), Pasal 45 ayat (4), Pasal 45 ayat (5), Pasa…
- catatan: Pasal II UU 1/2024 (chunk ketentuan_penutup)

## Q6. Apa yang dimaksud dengan Penyelenggara Sistem Elektronik?

- parse: {'pasal': None, 'ayat': None, 'tanggal': '2026-11-12', 'router': 'definisi'}
- diharapkan: ['uu-2008-11#pasal-1@uu-2016-19::angka-6a']
- ✅ terambil (top-3): ['uu-2008-11#pasal-1@uu-2016-19::angka-6a', 'uu-2008-11#pasal-1@uu-2016-19::angka-6', 'uu-2008-11#pasal-1@uu-2016-19::angka-10']
- top-1 header: `UU 11/2008 (ITE, diubah UU 1/2024) › BAB I Ketentuan Umum › Pasal 1 angka 6a [bunyi menurut UU 19/2016 · berlaku 2016-11-25 s.d. sekarang]`
- top-1 teks: Dalam Undang-Undang ini yang dimaksud dengan: 6a. Penyelenggara Sistem Elektronik adalah setiap Orang, penyelenggara negara, Badan Usaha, dan masyarakat yang menyediakan, mengelola, dan/atau mengoperasikan Sistem Elektro…
- catatan: Definisi disisipkan UU 19/2016 (angka 6a)
