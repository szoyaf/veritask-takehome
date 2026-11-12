"""Bagian 2: metadata schema (Pydantic v2) for regulation level and pasal level.

Every field carries `asal` (provenance) in its JSON Schema:
  ekstraksi        read directly from the document text (regex over the structured JSON)
  turunan          computed from other fields / relations (never typed by hand)
  model            output of a classifier (here: keyword rules, not an LLM) — treat as a guess
  sumber           acquisition metadata (URL, download date, file hash)
  manual_eksternal entered by hand from an outside source, with that source cited
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def F(asal: str, desc: str, **kw):
    return Field(description=desc, json_schema_extra={"asal": asal}, **kw)


class JenisPeraturan(str, Enum):
    """Daftar baku jenis peraturan (UU 12/2011 jo. UU 13/2022, Pasal 7-8)."""
    UUD = "UUD"
    TAP_MPR = "TAP MPR"
    UU = "UU"
    PERPPU = "Perppu"
    PP = "PP"
    PERPRES = "Perpres"
    PERDA_PROV = "Perda Provinsi"
    PERDA_KAB = "Perda Kabupaten/Kota"
    PERMEN = "Permen"
    PERBAN = "Peraturan Badan/Lembaga"


class StatusPeraturan(str, Enum):
    berlaku = "berlaku"
    diubah = "diubah"
    dicabut = "dicabut"
    dicabut_sebagian = "dicabut_sebagian"


class StatusPasal(str, Enum):
    berlaku = "berlaku"
    diubah = "diubah"                 # berlaku, tetapi bunyinya sudah pernah diubah
    berlaku_sebagian = "berlaku_sebagian"  # sebagian ayat sudah tidak berlaku
    tidak_berlaku = "tidak_berlaku"
    dihapus = "dihapus"
    belum_berlaku = "belum_berlaku"


class Bidang(BaseModel):
    label: str
    skor: float = Field(ge=0, le=1, description="share of keyword hits, not a calibrated probability")
    metode: Literal["keyword_rules_v1"] = "keyword_rules_v1"


# ------------------------------------------------------------------ level peraturan
class PeraturanMetadata(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str = F("turunan", "ID stabil `<jenis>-<tahun>-<nomor>`, dibentuk ulang dari jenis/tahun/nomor", pattern=r"^[a-z]+-\d{4}-\d+$")
    jenis: JenisPeraturan = F("ekstraksi", "Jenis peraturan (daftar baku)")
    nomor: int = F("ekstraksi", "Nomor peraturan")
    tahun: int = F("ekstraksi", "Tahun peraturan")
    judul: str = F("ekstraksi", "Judul lengkap, mis. 'Undang-Undang Nomor 1 Tahun 2024 tentang Perubahan Kedua atas ...'")
    tentang: str = F("turunan", "Subjek inti untuk pencarian (frasa 'tentang' terakhir di judul)")
    judul_singkat: str = F("turunan", "Label pendek untuk header chunk, mis. 'UU 1/2024'")
    jenis_struktur: Literal["induk", "perubahan"] = F("turunan", "UU induk atau UU perubahan (dari ada/tidaknya 'Pasal I' + butir)")
    pembentuk: list[str] = F("ekstraksi", "Lembaga pembentuk dari 'Dengan Persetujuan Bersama ...'")
    pemrakarsa: Optional[str] = F("ekstraksi", "Pemrakarsa bila disebut di dokumen; UU tidak menyebutnya -> null")
    penandatangan: Optional[str] = F("ekstraksi", "Nama pejabat yang mengesahkan")
    jabatan_penandatangan: Optional[str] = F("ekstraksi", "Jabatan pejabat yang mengesahkan")
    pengundang: Optional[str] = F("ekstraksi", "Nama menteri yang mengundangkan")
    jabatan_pengundang: Optional[str] = F("ekstraksi", "Jabatan menteri yang mengundangkan")
    tanggal_ditetapkan: date = F("ekstraksi", "Tanggal disahkan/ditetapkan (ISO 8601)")
    tanggal_diundangkan: date = F("ekstraksi", "Tanggal diundangkan (ISO 8601) — bisa beda dari ditetapkan")
    tanggal_berlaku: Optional[date] = F("turunan", "Dari klausul 'mulai berlaku pada tanggal diundangkan' (Pasal penutup / Pasal II)")
    dasar_tanggal_berlaku: Optional[str] = F("ekstraksi", "Kalimat sumber tanggal_berlaku")
    lembaran_negara: Optional[str] = F("ekstraksi", "Persis dari dokumen, mis. 'LN Tahun 2024 Nomor 1'")
    tambahan_lembaran_negara: Optional[str] = F("ekstraksi", "Persis dari dokumen, mis. 'TLN Nomor 6905'")
    status: StatusPeraturan = F("turunan", "Diturunkan dari relasi masuk (mengubah/mencabut), bukan diisi manual")
    status_per_tanggal: date = F("turunan", "Tanggal acuan perhitungan status")
    mengubah: list[str] = F("turunan", "ID peraturan yang diubah oleh peraturan ini (dari relasi)")
    diubah_oleh: list[str] = F("turunan", "ID peraturan yang mengubah peraturan ini (dari relasi)")
    dasar_hukum: list[str] = F("turunan", "ID peraturan di bagian Mengingat (dari relasi dasar_hukum)")
    jumlah_pasal: int = F("turunan", "Jumlah pasal di batang tubuh (UU perubahan: pasal yang dimuat di butir)")
    bidang: list[Bidang] = F("model", "Topik hasil klasifikasi kata kunci — HASIL MODEL, bukan fakta dokumen")
    sumber_url: str = F("sumber", "URL unduhan PDF resmi (JDIH BPK)")
    halaman_sumber: Optional[str] = F("sumber", "Halaman detail peraturan di JDIH")
    tanggal_unduh: date = F("sumber", "Tanggal unduh")
    hash_file: str = F("sumber", "sha256 file PDF untuk audit & deteksi perubahan", pattern=r"^sha256:[0-9a-f]{64}$")
    jumlah_halaman: int = F("sumber", "Jumlah halaman PDF")
    metode_ekstraksi: str = F("sumber", "Backend ekstraksi teks yang dipakai")
    lapisan_teks: Literal["digital", "ocr_bawaan"] = F("turunan", "Teks digital asli atau OCR bawaan penerbit (dari luas halaman yang tertutup gambar)")


# ------------------------------------------------------------------ level pasal (per versi)
class Unit(BaseModel):
    jenis: Literal["ayat", "huruf", "angka"]
    nomor: str
    teks: str
    anak: list["Unit"] = []
    berlaku_sampai: Optional[date] = None


class Penjelasan(BaseModel):
    teks: str = F("ekstraksi", "Teks Penjelasan Pasal demi Pasal untuk pasal ini")
    sumber_peraturan: str = F("turunan", "UU yang memuat penjelasan ini (bisa lebih lama dari bunyi pasal bila tidak diubah)")


class PasalMetadata(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    pasal_id: str = F("turunan", "ID pasal stabil, mis. 'uu-2008-11#pasal-27'", pattern=r"^[a-z]+-\d{4}-\d+#pasal-\d+[A-Z]?$")
    versi_id: str = F("turunan", "ID versi, '<pasal_id>@<peraturan yang menetapkan bunyi ini>'")
    peraturan_id: str = F("turunan", "Peraturan tempat pasal ini berada (UU terkonsolidasi)")
    nomor: str = F("ekstraksi", "Nomor pasal, mis. '27', '27A'")
    bab: Optional[str] = F("ekstraksi", "BAB induk, mis. 'BAB VII Perbuatan yang Dilarang' (pasal sisipan: BAB pasal asalnya)")
    bagian: Optional[str] = F("ekstraksi", "Bagian induk bila ada")
    paragraf: Optional[str] = F("ekstraksi", "Paragraf induk bila ada")
    teks: str = F("ekstraksi", "Bunyi lengkap pasal versi ini")
    ayat: list[Unit] = F("ekstraksi", "Struktur ayat > huruf > angka")
    penjelasan: Optional[Penjelasan] = F("ekstraksi", "Penjelasan Pasal demi Pasal yang ditautkan ke pasal ini (null bila tidak ada)", default=None)
    ditetapkan_oleh: str = F("turunan", "Peraturan yang menetapkan bunyi versi ini")
    butir_perubahan: Optional[str] = F("ekstraksi", "Nomor butir di Pasal I UU perubahan")
    jenis_perubahan: Literal["asli", "isi", "penjelasan", "sisipan", "dihapus"] = F("turunan", "Apa yang berubah pada versi ini")
    berlaku_sejak: date = F("turunan", "tanggal_berlaku peraturan penetap")
    berlaku_sampai: Optional[date] = F("turunan", "Mulai berlakunya versi berikut / batas keberlakuan; null = masih berlaku")
    sebab_berakhir: Optional[str] = F("turunan", "Relasi yang mengakhiri versi ini bila bukan versi berikutnya")
    ayat_tidak_berlaku: list[str] = F("turunan", "Ayat yang sudah tidak berlaku per status_per_tanggal")
    status: StatusPasal = F("turunan", "Diturunkan dari relasi per status_per_tanggal")
    status_per_tanggal: date = F("turunan", "Tanggal acuan status")
    diubah_terakhir_oleh: Optional[str] = F("turunan", "Peraturan terakhir yang mengubah pasal ini (semua versi)")
    versi_sebelumnya: Optional[str] = F("turunan", "versi_id yang digantikan")
    merujuk: list[str] = F("turunan", "pasal_id yang dirujuk teks versi ini")
    dirujuk_oleh: list[str] = F("turunan", "versi_id lain yang merujuk pasal ini")
    mendelegasikan: list[str] = F("turunan", "Jenis peraturan pelaksana yang didelegasikan")
    bidang: list[Bidang] = F("model", "Topik hasil klasifikasi kata kunci — HASIL MODEL")
    halaman: Optional[int] = F("sumber", "Halaman PDF peraturan penetap tempat pasal mulai")


Unit.model_rebuild()
