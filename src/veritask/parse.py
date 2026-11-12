"""Rebuild the legal hierarchy of an Indonesian Undang-Undang from cleaned lines.

Output (dict, JSON-serialisable):
  judul_dokumen, konsiderans{menimbang[], mengingat[]}, diktum{memutuskan, menetapkan},
  batang_tubuh[]   original act : BAB > Bagian > Paragraf > Pasal > ayat > huruf > angka
                   amending act : Pasal I > butir perubahan > (Pasal ...) ; Pasal II
  penutup{teks}, penjelasan{umum, pasal_demi_pasal[]}, tln
Every node: {"type", "nomor", "judul"?, "teks", "children", "halaman"}.

Design choice: rules + sequence checks, no ML. A list marker is accepted only when it is the
*next expected* number/letter for some open container (e.g. "(3)" after "(2)", "c." after "b.").
That alone rejects most false markers coming from wrapped references ("... Pasal 27 ayat\n(1)").
"""
from __future__ import annotations

import re
from typing import Any

from .clean import Line, fix_number_token, join_text, normalise

Node = dict[str, Any]

RE_BAB = re.compile(r"^BAB\s+([IVXLC]+)\s*$")
RE_BAGIAN = re.compile(r"^Bagian\s+(Ke[a-z]+)\s*$", re.I)
RE_PARAGRAF = re.compile(r"^Paragraf\s+(\d+)\s*$")
RE_PASAL = re.compile(r"^Pasal\s+(\d{1,3}[A-Z]?)\s*$")
RE_PASAL_ANY = re.compile(r"^Pasal\s+(\S{1,5})\s*$")  # incl. OCR-garbled / roman
RE_ROMAN_PASAL = re.compile(r"^Pasal\s+(I|II|III|IV|V)\s*$")
RE_BUTIR = re.compile(
    r"^(\d{1,2})[.,]?\s+(Ketentuan|Di\s?antara|Penjelasan|Judul|Pasal|Setelah|Bab|BAB|Bagian|Lampiran|Menambahkan)\b"
)

MARKERS = {
    "ayat": re.compile(r"^\((\d{1,2}[a-z]?)\)\s*(.*)$"),
    "huruf": re.compile(r"^([a-z])[.]\s+(.*)$"),
    "angka": re.compile(r"^(\d{1,2}[a-z]?)[.]\s+(.*)$"),
}
MARKERS_LOOSE = {  # OCR dropped the dot: "b bahwa", "2 Undang-Undang"
    "huruf": re.compile(r"^([a-z])\s+(.*)$"),
    "angka": re.compile(r"^(\d{1,2}[a-z]?)\s+([A-Z].*)$"),
}
LEVEL = {"ayat": 1, "huruf": 2, "angka": 3}


def iter_pasal(nodes: list[Node]):
    """Yield (pasal_node, ancestors) for every pasal of a batang_tubuh tree, in document order."""
    stack = [(n, []) for n in reversed(nodes)]
    while stack:
        n, anc = stack.pop()
        if n["type"] == "pasal":
            yield n, anc
            continue
        for c in reversed(n.get("children", [])):
            stack.append((c, anc + [n]))


def node(type_: str, nomor: str | None = None, teks: str = "", page: int | None = None, **kw) -> Node:
    n = {"type": type_, "nomor": nomor, "teks": teks, "children": [], "halaman": page}
    n.update(kw)
    return n


# ------------------------------------------------------------------ sequence helpers
def _split_num(s: str) -> tuple[int, str]:
    m = re.fullmatch(r"(\d+)([a-z]?)", s)
    return (int(m.group(1)), m.group(2)) if m else (-1, "")


def _is_next(kind: str, prev: str | None, cur: str) -> bool:
    if kind == "huruf":
        return cur == "a" if prev is None else ord(cur) == ord(prev) + 1
    pn, ps = _split_num(prev) if prev else (0, "")
    cn, cs = _split_num(cur)
    if prev is None:
        return cn == 1 and cs == ""
    if cn == pn + 1 and cs == "":
        return True
    if cn == pn and cs and cs == (chr(ord(ps) + 1) if ps else "a"):  # inserted "2a", "2b"
        return True
    return False


def _match_marker(text: str, loose: bool) -> list[tuple[str, str, str]]:
    out = []
    for kind, rx in MARKERS.items():
        m = rx.match(text)
        if m:
            out.append((kind, m.group(1), m.group(2)))
    if loose and not out:
        for kind, rx in MARKERS_LOOSE.items():
            m = rx.match(text)
            if m:
                out.append((kind, m.group(1), m.group(2)))
    return out


# ------------------------------------------------------------------ pasal body
def parse_items(root: Node, lines: list[Line], loose: bool = False) -> Node:
    """Attach ayat/huruf/angka children to `root` from body lines. Sets root['teks'] to the full
    text (markers included) and each child's 'teks' to its own text without descendants."""
    buf: dict[int, list[str]] = {id(root): []}
    chain: list[Node] = [root]  # root .. deepest open item

    def last_child(container: Node, kind: str) -> str | None:
        for c in reversed(container["children"]):
            if c["type"] == kind:
                return c["nomor"]
        return None

    for ln in lines:
        placed = False
        for kind, num, rest in _match_marker(ln.text, loose):
            for depth in range(len(chain) - 1, -1, -1):
                cont = chain[depth]
                prev = last_child(cont, kind)
                if prev is None:
                    other_kinds = [c for c in cont["children"] if c["type"] != kind]
                    cont_txt = join_text(buf[id(cont)])
                    opens_list = cont_txt.endswith(":") or (cont is root and not cont_txt and not other_kinds)
                    if not (_is_next(kind, None, num) and opens_list and not other_kinds):
                        continue
                elif not _is_next(kind, prev, num):
                    continue
                if cont is not root and LEVEL.get(cont["type"], 0) >= LEVEL[kind] and prev is None:
                    continue
                item = node(kind, num, page=ln.page)
                cont["children"].append(item)
                buf[id(item)] = [rest]
                del chain[depth + 1 :]
                chain.append(item)
                placed = True
                break
            if placed:
                break
        if not placed:
            buf[id(chain[-1])].append(ln.text)

    def finalise(n: Node) -> None:
        n["teks"] = join_text(buf.get(id(n), []))
        for c in n["children"]:
            finalise(c)

    finalise(root)
    root["teks_lengkap"] = join_text([l.text for l in lines])
    return root


# ------------------------------------------------------------------ document sections
def _find(lines: list[Line], rx: str, start: int = 0, end: int | None = None, flags=0) -> int:
    r = re.compile(rx, flags)
    for i in range(start, len(lines) if end is None else end):
        if r.search(lines[i].text):
            return i
    return -1


def _strip_label(text: str, label: str) -> str:
    return normalise(re.sub(rf"^{label}\s*:?\s*", "", text))


def parse_document(lines: list[Line]) -> dict:
    i_menimbang = _find(lines, r"^Menimbang")
    i_mengingat = _find(lines, r"^Mengingat", i_menimbang + 1)
    i_persetujuan = _find(lines, r"^Dengan Persetujuan", i_mengingat + 1)
    i_memutuskan = _find(lines, r"^MEMUTUSKAN", i_mengingat + 1)
    i_menetapkan = _find(lines, r"^Menetapkan", i_memutuskan + 1)
    i_agar = _find(lines, r"^Agar setiap orang", i_menetapkan + 1)
    i_penj = _find(lines, r"^PENJELASAN\s*$", i_agar + 1)

    # body starts at first BAB / Pasal heading after Menetapkan
    i_body = next(
        i for i in range(i_menetapkan + 1, len(lines)) if RE_BAB.match(lines[i].text) or RE_PASAL_ANY.match(lines[i].text)
    )
    doc: dict[str, Any] = {}
    doc["judul_dokumen"] = join_text([l.text for l in lines[:i_menimbang] if not re.match(r"^(DENGAN RAHMAT|PRESIDEN REPUBLIK)", l.text)])

    menimbang = [Line(_strip_label(lines[i_menimbang].text, "Menimbang"), lines[i_menimbang].page)] + lines[i_menimbang + 1 : i_mengingat]
    mengingat = [Line(_strip_label(lines[i_mengingat].text, "Mengingat"), lines[i_mengingat].page)] + lines[
        i_mengingat + 1 : (i_persetujuan if i_persetujuan > 0 else i_memutuskan)
    ]
    doc["konsiderans"] = {
        "menimbang": parse_items(node("menimbang"), menimbang, loose=True),
        "mengingat": parse_items(node("mengingat"), mengingat, loose=True),
    }
    doc["diktum"] = {
        "persetujuan_bersama": join_text([l.text for l in lines[i_persetujuan:i_memutuskan]]) if 0 < i_persetujuan < i_memutuskan else None,
        "memutuskan": "MEMUTUSKAN:",
        "menetapkan": join_text([_strip_label(lines[i_menetapkan].text, "Menetapkan")] + [l.text for l in lines[i_menetapkan + 1 : i_body]]),
    }
    body = lines[i_body:i_agar]
    is_amendment = bool(RE_ROMAN_PASAL.match(body[0].text))
    doc["jenis_struktur"] = "perubahan" if is_amendment else "induk"
    doc["batang_tubuh"] = parse_amendment_body(body) if is_amendment else parse_original_body(body)

    pen_end = i_penj if i_penj > 0 else len(lines)
    doc["penutup"] = {"teks": join_text([l.text for l in lines[i_agar:pen_end]]), "halaman": lines[i_agar].page}
    doc["penjelasan"] = parse_penjelasan(lines[i_penj:], is_amendment) if i_penj > 0 else None
    return doc


# ------------------------------------------------------------------ original act body
def _title_lines(body: list[Line], i: int) -> tuple[str, int]:
    """Collect the title after a BAB/Bagian/Paragraf heading (body[i - 1]). Bagian and Paragraf
    titles are one line; BAB titles are upper-case and may wrap over several lines."""
    sub_heading = RE_BAGIAN.match(body[i - 1].text) or RE_PARAGRAF.match(body[i - 1].text)
    title = []
    j = i
    while j < len(body):
        t = body[j].text
        if RE_PASAL.match(t) or RE_BAGIAN.match(t) or RE_PARAGRAF.match(t) or RE_BAB.match(t):
            break
        title.append(t)
        j += 1
        if sub_heading or not t.isupper():
            break
    return join_text(title), j


def pasal_key(n: str) -> tuple[int, str]:
    m = re.fullmatch(r"(\d+)([A-Z]?)", n)
    return (int(m.group(1)), m.group(2)) if m else (-1, "")


def parse_original_body(body: list[Line]) -> list[Node]:
    root: list[Node] = []
    bab = bagian = paragraf = None
    pasal: Node | None = None
    pasal_lines: list[Line] = []
    last_key = (0, "")

    def close_pasal():
        nonlocal pasal, pasal_lines
        if pasal is not None:
            parse_items(pasal, pasal_lines)
        pasal, pasal_lines = None, []

    def container() -> list[Node]:
        for c in (paragraf, bagian, bab):
            if c is not None:
                return c["children"]
        return root

    i = 0
    while i < len(body):
        ln = body[i]
        t = ln.text
        if m := RE_BAB.match(t):
            close_pasal()
            judul, i = _title_lines(body, i + 1)
            bab = node("bab", m.group(1), page=ln.page, judul=judul)
            bagian = paragraf = None
            root.append(bab)
            continue
        # "Bagian Kedua" opens a new Bagian unless it is wrapped text inside an unfinished pasal sentence
        if (m := RE_BAGIAN.match(t)) and (pasal is None or (pasal_lines and pasal_lines[-1].text.endswith("."))):
            close_pasal()
            judul, i = _title_lines(body, i + 1)
            bagian = node("bagian", m.group(1).capitalize(), page=ln.page, judul=judul)
            paragraf = None
            (bab["children"] if bab else root).append(bagian)
            continue
        if m := RE_PARAGRAF.match(t):
            close_pasal()
            judul, i = _title_lines(body, i + 1)
            paragraf = node("paragraf", m.group(1), page=ln.page, judul=judul)
            (bagian or bab or {"children": root})["children"].append(paragraf)
            continue
        if (m := RE_PASAL.match(t)) and pasal_key(m.group(1)) > last_key:
            close_pasal()
            last_key = pasal_key(m.group(1))
            pasal = node("pasal", m.group(1), page=ln.page)
            container().append(pasal)
            i += 1
            continue
        if pasal is not None:
            pasal_lines.append(ln)
        i += 1
    close_pasal()
    return root


# ------------------------------------------------------------------ amending act body
def butir_targets(instr: str) -> dict:
    """Read the amendment instruction of one butir: action + target pasal(s)."""
    info: dict[str, Any] = {"aksi": [], "pasal_target": [], "pasal_baru": []}
    m = re.search(r"Di\s?antara Pasal (\d+[A-Z]?) dan Pasal (\d+[A-Z]?) disisipkan (\d+)\s*\(\w+\)\s*pasal", instr, re.I)
    if m:
        base, n = m.group(1), int(m.group(3))
        info["aksi"].append("menyisipkan_pasal")
        info["pasal_baru"] = [base + chr(ord("A") + k) for k in range(n)]
        info["sisip_antara"] = [m.group(1), m.group(2)]
    if re.search(r"\bdiubah\b", instr):
        info["aksi"].append("mengubah")
    if re.search(r"\bdihapus\b", instr):
        info["aksi"].append("menghapus")
    if re.search(r"disisipkan \d+\s*\(\w+\)\s*(ayat|angka|huruf)", instr):
        info["aksi"].append("menyisipkan_bagian_pasal")
    if re.search(r"ditambah\w*\s+\d+\s*\(\w+\)\s*(ayat|angka|huruf)", instr):
        info["aksi"].append("menambah_bagian_pasal")
    if re.search(r"tetap dengan perubahan penjelasan", instr):
        info["aksi"].append("mengubah_penjelasan")
    elif re.match(r"Penjelasan\b", instr):
        info["aksi"].append("mengubah_penjelasan")
    m2 = re.search(r"sehingga Pasal (\d+[A-Z]?) berbunyi", instr)
    # pasal changed in place = those named before any "di antara Pasal X dan Pasal Y disisipkan"
    head = re.split(r"\bdi\s?antara Pasal", instr, flags=re.I)[0]
    mentioned = re.findall(r"Pasal (\d+[A-Z]?)", head)
    if m2:
        info["pasal_target"] = [m2.group(1)]
    else:
        info["pasal_target"] = list(dict.fromkeys(mentioned))
    return info


def _resolve_heading(raw: str, expected: list[str], seen: set[str]) -> str | None:
    """Map an OCR-garbled content heading ("168", "I") to an expected pasal number."""
    if raw in expected:
        return raw
    fixed = fix_number_token(raw) if raw not in {"I", "II"} else raw.replace("I", "1")
    if fixed in expected:
        return fixed
    pending = [e for e in expected if e not in seen]
    num = re.match(r"\d+", fixed)
    for e in pending:  # same numeric root, suffix garbled (16B read as 168, 27B as 278)
        if num and re.match(r"\d+", e) and fixed.startswith(re.match(r"\d+", e).group(0)):
            return e
    return None


def parse_amendment_body(body: list[Line]) -> list[Node]:
    out: list[Node] = []
    roman: Node | None = None
    roman_lines: list[Line] = []
    butir: Node | None = None
    instr_lines: list[Line] = []
    pasal: Node | None = None
    pasal_lines: list[Line] = []
    expected: list[str] = []
    seen: set[str] = set()
    n_butir = 0

    def close_pasal():
        nonlocal pasal, pasal_lines
        if pasal is not None:
            parse_items(pasal, pasal_lines)
        pasal, pasal_lines = None, []

    def set_instruction() -> list[str]:
        """Close the instruction text of the current butir; return the pasal it should contain."""
        butir["instruksi"] = join_text([l.text for l in instr_lines])
        butir.update(butir_targets(butir["instruksi"]))
        return butir["pasal_baru"] + butir["pasal_target"]

    def close_butir():
        nonlocal butir, instr_lines
        close_pasal()
        if butir is not None and "instruksi" not in butir:
            set_instruction()
        butir, instr_lines = None, []

    for ln in body:
        t = ln.text
        mr = RE_ROMAN_PASAL.match(t)
        # a later "Pasal I" is OCR of "Pasal 1" inside content; "Pasal II" only after the butir list
        if mr and (roman is None or (mr.group(1) != "I" and n_butir > 0 and not (butir and pasal is None and "instruksi" not in butir))):
            close_butir()
            if roman is not None:
                roman["teks"] = join_text([l.text for l in roman_lines])
            roman = node("pasal_romawi", mr.group(1), page=ln.page)
            roman_lines = []
            out.append(roman)
            continue
        mb = RE_BUTIR.match(t)
        if roman is not None and roman["nomor"] == "I" and mb and int(mb.group(1)) == n_butir + 1 and (
            pasal is None or not pasal_lines or re.search(r"[.;:]$", pasal_lines[-1].text) or butir is None
        ):
            close_butir()
            n_butir += 1
            butir = node("butir", str(n_butir), page=ln.page)
            roman["children"].append(butir)
            instr_lines = [Line(t[mb.end(1):].lstrip(".,").strip(), ln.page)]
            expected, seen = [], set()
            continue
        mp = RE_PASAL_ANY.match(t)
        if butir is not None and mp:
            if "instruksi" not in butir:
                expected = set_instruction()
            key = _resolve_heading(mp.group(1), expected, seen)
            if key:
                close_pasal()
                seen.add(key)
                pasal = node("pasal", key, page=ln.page, nomor_ocr=mp.group(1) if mp.group(1) != key else None)
                butir["children"].append(pasal)
                continue
        if butir is not None:
            if pasal is not None:
                pasal_lines.append(ln)
            elif "instruksi" not in butir:
                instr_lines.append(ln)
            else:
                pasal_lines.append(ln)
        elif roman is not None:
            roman_lines.append(ln)
    close_butir()
    if roman is not None and not roman.get("teks"):
        roman["teks"] = join_text([l.text for l in roman_lines])
    for r in out:  # pembuka text of Pasal I = lines before first butir
        r.setdefault("teks", "")
    return out


# ------------------------------------------------------------------ penjelasan
RE_P_AYAT = re.compile(r"^Ayat\s*\(?(\d{1,2}[a-z]?)\)?\s*$")
RE_P_HURUF = re.compile(r"^Huruf\s+([a-z])\s*$")
RE_P_ANGKA = re.compile(r"^Angka\s+(\d{1,2}[a-z]?)\s*(?:(Pasal\s+\S+))?\s*$")


def parse_penjelasan(lines: list[Line], is_amendment: bool) -> dict:
    i_umum = _find(lines, r"^(I\.?\s*)?UMUM\s*$")
    i_pdp = _find(lines, r"PASAL DEMI PASAL")
    i_tln = _find(lines, r"^TAMBAHAN LEMBARAN NEGARA")
    end = i_tln if i_tln > 0 else len(lines)
    umum = [l.text for l in lines[i_umum + 1 : i_pdp] if not re.fullmatch(r"II\.?", l.text)]
    out = {
        "judul": join_text([l.text for l in lines[: max(i_umum, 0)]]),
        "umum": join_text(umum),
        "pasal_demi_pasal": [],
        "tln_raw": lines[i_tln].text if i_tln > 0 else None,
    }
    entries: list[Node] = []
    cur: Node | None = None
    cur_lines: list[Line] = []
    angka: str | None = None
    roman: str | None = None
    last_key = (0, "")

    def close():
        nonlocal cur, cur_lines
        if cur is not None:
            _parse_penj_entry(cur, cur_lines)
        cur, cur_lines = None, []

    for ln in lines[i_pdp + 1 : end]:
        t = ln.text
        if is_amendment and (m := RE_ROMAN_PASAL.match(t)) and m.group(1) in {"I", "II"} and (roman is None or m.group(1) == "II"):
            close()
            roman = m.group(1)
            angka = None
            if roman == "II":
                cur = node("penjelasan_pasal", "II", page=ln.page, pasal_romawi="II")
                entries.append(cur)
            continue
        if is_amendment and (m := RE_P_ANGKA.match(t)) and roman == "I":
            close()
            angka = m.group(1)
            if m.group(2):
                t = m.group(2)
            else:
                continue
        mp = RE_PASAL_ANY.match(t)
        if mp:
            raw = mp.group(1)
            key = raw if RE_PASAL.match(t) else fix_number_token(raw)
            ok = re.fullmatch(r"\d{1,3}[A-Z]?" if not is_amendment else r"\d{1,3}[A-Za-z]{0,2}", key or "")
            if ok and (is_amendment or pasal_key(key) > last_key):
                close()
                last_key = pasal_key(key)
                cur = node("penjelasan_pasal", key, page=ln.page, butir=angka, nomor_ocr=raw if raw != key else None)
                entries.append(cur)
                continue
        if cur is not None:
            cur_lines.append(ln)
    close()
    out["pasal_demi_pasal"] = entries
    return out


def _parse_penj_entry(entry: Node, lines: list[Line]) -> None:
    """Penjelasan sub-headings: 'Ayat (1)' > 'Huruf a' > 'Angka 1', each followed by text."""
    stack: list[Node] = [entry]
    buf: dict[int, list[str]] = {id(entry): []}
    for ln in lines:
        for kind, rx in (("ayat", RE_P_AYAT), ("huruf", RE_P_HURUF), ("angka", RE_P_ANGKA)):
            m = rx.match(ln.text)
            if m:
                while len(stack) > 1 and LEVEL[stack[-1]["type"]] >= LEVEL[kind]:
                    stack.pop()
                item = node(kind, m.group(1), page=ln.page)
                stack[-1]["children"].append(item)
                stack.append(item)
                buf[id(item)] = []
                break
        else:
            buf[id(stack[-1])].append(ln.text)

    def fin(n: Node):
        n["teks"] = join_text(buf.get(id(n), []))
        for c in n["children"]:
            fin(c)

    fin(entry)
    entry["teks_lengkap"] = join_text([l.text for l in lines])
