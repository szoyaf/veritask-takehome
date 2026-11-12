"""Page-level noise removal and OCR normalisation.

Input: list of raw page strings. Output: list of Line(text, page) with
  - running header (kop "PRESIDEN REPUBLIK INDONESIA", garbled OCR variants), page numbers,
    "SALINAN", "SK No ..." stamps removed,
  - page-end catchwords ("Pasal 4 . . .", "(2) Ketentuan . .") removed,
  - common OCR confusions in structural tokens fixed ("(21" -> "(2)", "Pasal2TA" -> "Pasal 27A",
    "(l)" -> "(1)", "2O08" -> "2008", "dan/ atau" -> "dan/atau"),
  - lone list markers ("a.", "(4)", "1.") merged with the following line.
Every rule is deliberately narrow (anchored on structural context) so it does not touch prose.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz


@dataclass
class Line:
    text: str
    page: int  # 1-based


# ---------------------------------------------------------------- page level
PAGE_NO = re.compile(r"^-\s*[\dlIOot]{1,3}\s*[t]?\s*-?$|^-?\s*\d{1,2}\s*-$|^-$")
SK_STAMP = re.compile(r"^SK\s*No\b", re.I)
DOTS_ONLY = re.compile(r"^[.\s…]*$")
CATCHWORD_END = re.compile(r"(\.\s*\.(\s*\.)?|…)\s*$")
STRUCTURAL = re.compile(
    r"^(BAB\b|Pasal\b|Bagian\b|Paragraf\b|\(\w{1,3}\)|[a-z]\.\s|\d{1,2}\.\s|UNDANG|PENJELASAN|"
    r"Menimbang|Mengingat|MEMUTUSKAN|Menetapkan|Agar\b|Disahkan|Diundangkan)"
)


def _is_header_noise(s: str) -> bool:
    t = s.strip()
    if not t:
        return True
    if STRUCTURAL.match(t):
        return False
    up = t.upper()
    if fuzz.ratio(up, "PRESIDEN") >= 60 or fuzz.ratio(up, "REPUBLIK INDONESIA") >= 60:
        return True
    if fuzz.ratio(up, "PRESIDEN REPUBLIK INDONESIA") >= 70 and len(t) < 35:
        return True
    if up == "SALINAN":
        return True
    # garbled OCR of the kop: no space-separated lowercase words, short
    words = re.findall(r"[a-z]{3,}", t)
    if len(t) <= 30 and not re.search(r"[a-z]{3,}\s+[a-z]{3,}", t) and len(words) <= 2:
        return True
    return False


def strip_page(raw: str, page_no: int) -> list[str]:
    lines = [l.rstrip() for l in raw.splitlines()]
    lines = [l for l in lines if not SK_STAMP.match(l.strip())]
    # --- header: drop everything up to the page-number line if it is near the top
    head = lines[:8]
    cut = None
    for i, l in enumerate(head):
        s = l.strip()
        if PAGE_NO.match(s) or re.match(r"^_\s*\w{1,3}\s*-?$", s):
            cut = i
        # bare "11" on its own line, right after kop / "-" lines
        elif re.fullmatch(r"\d{1,2}", s) and all(_is_header_noise(x) or x.strip() == "-" for x in head[:i]):
            cut = i
    if cut is not None:
        lines = lines[cut + 1 :]
        while lines and (lines[0].strip() in {"-", ""} or PAGE_NO.match(lines[0].strip())):
            lines = lines[1:]
    else:  # first page of the act / of the Penjelasan: drop kop lines only
        while lines and _is_header_noise(lines[0]):
            lines = lines[1:]
    # --- footer: catchword that repeats the first words of the next page
    while lines and DOTS_ONLY.match(lines[-1]):
        lines.pop()
    if lines and CATCHWORD_END.search(lines[-1]) and len(lines[-1].strip()) < 45:
        lines.pop()
    elif len(lines) >= 2 and DOTS_ONLY.match(lines[-2]) and len(lines[-1].strip()) < 20:
        lines = lines[:-2]  # "..." then a lone garbled catchword ("PasaJ2T")
    while lines and DOTS_ONLY.match(lines[-1]):
        lines.pop()
    return [l for l in lines if l.strip()]


# ---------------------------------------------------------------- OCR normalisation
_DIGITISH = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "i": "1", "T": "7", "S": "5", "s": "5", "t": "1"})


def fix_number_token(tok: str) -> str:
    """'2TA' -> '27A', '4OA' -> '40A', '3 1' -> '31'. Keeps a final A-H suffix letter."""
    tok = tok.replace(" ", "")
    m = re.fullmatch(r"([\dOolITSst]+?)([A-H]?)", tok)
    if not m or not re.search(r"\d", tok):
        return tok
    return m.group(1).translate(_DIGITISH) + m.group(2)


def _fix_pasal(m: re.Match) -> str:
    return "Pasal " + fix_number_token(m.group(1))


AYAT_OPEN = re.compile(r"^\(\s*(\d{1,2}[a-z]?)\s*\)")
AYAT_OCR = re.compile(r"^\(\s*([0-9lIsO]{1,2}?[a-z]?)\s*[1lIt\]}]?\s*(?=\s|$)")
INLINE_AYAT_OCR = re.compile(r"\bayat\s*[\(l]\s*([0-9lIsOL]{1,2}?[a-z]?)\s*[)1lIt\]}]?(?=[\s,.;:)]|$)")


def _ayat_num(s: str) -> str:
    return s.replace("l", "1").replace("I", "1").replace("L", "1").replace("O", "0").replace("s", "5")


def normalise(text: str) -> str:
    t = text
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace("dan/ atau", "dan/atau").replace("dan /atau", "dan/atau")
    t = re.sub(r"\bP\s?a\s?[sS]\s?a\s?[lJI1iT](?=[\s\dO]|$)", "Pasal", t)
    t = re.sub(r"^pasal\s+(?=\d)", "Pasal ", t)
    t = re.sub(r"\bPasil\b", "Pasal", t)
    # Pasal tokens: "Pasal2TA", "Pasal 4OA", "Pasal 3 1"
    t = re.sub(r"\bPasal\s*((?:\d[\dOolITSst]*|[OolI]\d[\dOolITSst]*)(?:\s\d\b)?[A-H]?)(?=[\s,.;:]|$)", _fix_pasal, t)
    t = re.sub(r"\bPasal(\d)", r"Pasal \1", t)
    # years / numbers with O/l mixed in: 2O08, 20O8, I1, 1l
    t = re.sub(r"\b(?=[\dOlI]*\d[\dOlI]*\d)[\dOlI]{3,4}\b", lambda m: m.group(0).translate(_DIGITISH), t)
    t = re.sub(r"\b(Nomor|NOMOR)\s+([Il1][Il1])\b", r"\1 11", t)
    t = re.sub(r"\b[Il] \((satu)\)", r"1 (\1)", t)
    # inline ayat references: "ayat (41," "ayal l2l" "ayat (ll,"
    t = re.sub(r"\baya[tl]\b", "ayat", t)
    t = INLINE_AYAT_OCR.sub(lambda m: f"ayat ({_ayat_num(m.group(1))})", t)
    t = re.sub(r"\(l\)", "(1)", t)
    # leading ayat marker: "l2l Penyidikan" -> "(2) ...", "(U Pemerintah" -> "(1) ..."
    t = re.sub(r"^l(\d{1,2}[a-z]?)l\s", r"(\1) ", t)
    t = re.sub(r"^[1l](\d[a-z]?)\)\s", r"(\1) ", t)  # "12) Penyidikan" -> "(2) Penyidikan"
    t = re.sub(r"^[tlI](\d)\.\s", r"1\1. ", t)  # "t7. Kontrak" -> "17. Kontrak"
    t = re.sub(r"^\([UIl|]\s", "(1) ", t)
    t = re.sub(r"^Angka(\d)", r"Angka \1", t)
    # leading ayat marker: "(21 Setiap" -> "(2) Setiap", "(2al" -> "(2a)"
    if t.startswith("(") and not AYAT_OPEN.match(t):
        m = re.match(r"^\(\s*([0-9lIsO]{1,2}?)([a-z]?)\s*[1lIt\]}]\s*", t) or re.match(
            r"^\(\s*([0-9lIsO]{1,2})([a-z]?)\s*\)?\s*", t
        )
        if m and re.search(r"[0-9lIsO]", m.group(1)):
            t = f"({_ayat_num(m.group(1))}{m.group(2)}) " + t[m.end():]
    # list markers with comma or missing dot: "a, bahwa" -> "a. bahwa", "2, Transaksi" -> "2. Transaksi"
    t = re.sub(r"^([a-z]),\s", r"\1. ", t)
    t = re.sub(r"^(\d{1,2}[a-z]?),\s", r"\1. ", t)
    # konsiderans labels mangled by OCR
    t = re.sub(r"^\S{0,3}(enimbang)\b\s*:?", "Menimbang :", t)
    t = re.sub(r"^Mengingat\s*:?\s*", "Mengingat : ", t)
    # penjelasan sub-headings: "Ang)<a 2" "Angka I"
    t = re.sub(r"^An\S{1,4}\s+([\dIl]{1,2})$", lambda m: "Angka " + _ayat_num(m.group(1)), t)
    t = re.sub(r"^Ayat\s*\(?\s*([0-9lIsO]{1,2}?[a-z]?)\s*[)1lIt\]}]?\s*\.{0,3}$", lambda m: f"Ayat ({_ayat_num(m.group(1))})", t)
    t = t.replace("Ayat(", "Ayat (")
    return t


LONE_MARKER = re.compile(r"^(\(\s*\w{1,3}\s*\)?|[a-z][.,]?|\d{1,2}[a-z]?[.,]?|Ayat|Angka|Huruf|\(\w{1,3}[1lt])$")


def clean_pages(pages: list[str]) -> list[Line]:
    stripped = [strip_page(raw, i) for i, raw in enumerate(pages, start=1)]
    # catchword without dots ("8. Ketentuan" at page end, repeated at top of next page)
    def squash(s: str) -> str:
        return re.sub(r"[\s.…]+", "", s)

    for i in range(len(stripped) - 1):
        cur, nxt = stripped[i], stripped[i + 1]
        if cur and nxt:
            last = squash(cur[-1])
            head = squash(" ".join(nxt[:2]))
            if 3 <= len(last) <= 30 and head.startswith(last):
                cur.pop()
    out = [Line(l, i) for i, page_lines in enumerate(stripped, start=1) for l in page_lines]
    # merge lone markers with the next line before normalising
    merged: list[Line] = []
    i = 0
    while i < len(out):
        cur = out[i]
        # lone "Pasal" + "1 Cukup jelas." -> "Pasal 1" / "Cukup jelas."
        if cur.text.strip() == "Pasal" and i + 1 < len(out):
            m = re.match(r"^(\d{1,3}[A-Z]?)(?:\s+(.*))?$", out[i + 1].text.strip())
            if m:
                merged.append(Line("Pasal " + m.group(1), cur.page))
                if m.group(2):
                    merged.append(Line(m.group(2), out[i + 1].page))
                i += 2
                continue
        if LONE_MARKER.match(cur.text.strip()) and i + 1 < len(out):
            nxt = out[i + 1]
            merged.append(Line(cur.text.strip() + " " + nxt.text.strip(), cur.page))
            i += 2
            continue
        merged.append(cur)
        i += 1
    normed = (Line(normalise(l.text), l.page) for l in merged)
    return [l for l in normed if l.text]


def join_text(lines: list[str]) -> str:
    """Join wrapped lines. Line-final hyphens in these acts are real hyphens
    ("Undang-/Undang", "kehati-/hatian"), so they are kept and the space dropped."""
    out = ""
    for l in lines:
        l = l.strip()
        if not l:
            continue
        if not out:
            out = l
        elif out.endswith("-") and not out.endswith(" -"):
            out += l
        else:
            out += " " + l
    return out
