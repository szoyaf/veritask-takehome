"""Dates, signatories and Lembaran Negara numbers from the penutup of an act.

Handles OCR-damaged month names ("Jarruari") and glued tokens ("Januari2024") by fuzzy
matching month names; returns ISO 8601 strings.
"""
from __future__ import annotations

import re

from rapidfuzz import process

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]
OCR_DIGITS = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "g": "8", "S": "5"})  # digits misread by OCR


def parse_tanggal(s: str) -> str | None:
    """'2 Jarruari 2024' / '2 Januari2024' / '25 November 2016' -> ISO date."""
    m = re.search(r"(\d{1,2})\s*([A-Za-z]{3,12})\s*([\dOolIgS]{4})", s)
    if not m:
        return None
    best = process.extractOne(m.group(2).capitalize(), BULAN, score_cutoff=60)
    if not best:
        return None
    month = BULAN.index(best[0]) + 1
    year = m.group(3).translate(OCR_DIGITS)
    return f"{year}-{month:02d}-{int(m.group(1)):02d}"


def parse_penutup(teks: str) -> dict:
    out: dict = {}
    m = re.search(r"Disahkan di (\w+) pada\s+tan\S*\s+(.{6,25}?\d{4})", teks)
    if m:
        out["tempat_ditetapkan"] = m.group(1)
        out["tanggal_ditetapkan"] = parse_tanggal(m.group(2))
    m = re.search(r"Diundangkan di (\w+) pada\s+tan\S*\s+(.{6,25}?\d{4})", teks)
    if m:
        out["tanggal_diundangkan"] = parse_tanggal(m.group(2))
    # signatory: the line after "PRESIDEN REPUBLIK INDONESIA," (optional "ttd")
    m = re.search(r"\d{4}\s+(PRESIDEN REPUBLIK INDONESIA),\s*(?:ttd\s+)?([A-Z][A-Z .,']+?)\s+Diundangkan", teks)
    if m:
        out["jabatan_penandatangan"] = "Presiden Republik Indonesia"
        out["penandatangan"] = m.group(2).strip().title()
    m = re.search(r"Diundangkan .*?\d{4}\s+(MENTERI [A-Z ]+?),?\s*(?:REPUBLIK INDONESIA,)?\s*(?:ttd\s+)?([A-Z][A-Z .']+?)\s+LEMBARAN", teks)
    if m:
        out["jabatan_pengundang"] = m.group(1).strip().title()
        out["pengundang"] = m.group(2).strip().title()
    m = re.search(r"LEMBARAN NEGARA REPUBLIK INDONESIA TAHUN (\d{4}) NOMOR (\d+)", teks)
    if m:
        out["lembaran_negara"] = f"LN Tahun {m.group(1)} Nomor {m.group(2)}"
    return out


def berlaku_rule(pasal_penutup_teks: str) -> str | None:
    """Return 'diundangkan' when the act says it takes effect on promulgation."""
    if re.search(r"mulai berlaku pada tanggal diundangkan", pasal_penutup_teks):
        return "diundangkan"
    return None
