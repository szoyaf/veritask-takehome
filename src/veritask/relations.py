"""Bagian 3: pasal-level relations between regulations (input for Graph RAG).

Method: deterministic rules over the structured JSON (no LLM). Every edge stores
  kutipan  - the trigger text it was read from,
  lokasi   - peraturan, butir / pasal / ayat, halaman,
  aturan   - which rule produced it (for auditing and per-rule precision).

Relations
  mengubah          peraturan -> pasal lama      "Ketentuan Pasal X diubah sehingga berbunyi"
                    (bagian='penjelasan' when only the Penjelasan changes)
  menyisipkan       peraturan -> pasal baru      "Di antara Pasal X dan Pasal Y disisipkan ... Pasal XA"
  menghapus         peraturan -> pasal lama      "Pasal X dihapus"
  mencabut          peraturan -> peraturan/pasal "... dicabut dan dinyatakan tidak berlaku"
  membatasi_keberlakuan  peraturan -> pasal/ayat "... berlaku sampai dengan diberlakukannya UU ..."
  dasar_hukum       peraturan -> peraturan       items of Mengingat
  merujuk           pasal(versi) -> pasal        "sebagaimana dimaksud dalam Pasal X ayat (1) [UU ...]"
  mendelegasikan    pasal(versi) -> jenis peraturan pelaksana  "diatur dengan/dalam Peraturan Pemerintah"
The amended act (UU 11/2008) is treated as the consolidated act: every pasal, including inserted
ones (27A, 45B ...), gets the stable id  uu-2008-11#pasal-<n>.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from .dates import OCR_DIGITS
from .parse import pasal_key

CONSOLIDATED = "uu-2008-11"  # the act being amended in this corpus


def pasal_id(per: str, nomor: str) -> str:
    return f"{per}#pasal-{nomor}"


def edge(src: str, dst: str, rel: str, aturan: str, kutipan: str, **lokasi: Any) -> dict:
    return {"source": src, "target": dst, "relasi": rel, "aturan": aturan,
            "kutipan": re.sub(r"\s+", " ", kutipan).strip()[:400], **{k: v for k, v in lokasi.items() if v is not None}}


# ------------------------------------------------------------------ law citations
_NUM = r"[\dOolIgS ]{1,5}?"
RE_LAW = re.compile(
    r"(?P<uud>Undang-Undang Dasar Negara Republik Indonesia Tahun 1945)"
    r"|(?P<kuhap>Undang-Undang tentang Hukum Acara Pidana|Kitab Undang-Undang Hukum Acara Pidana)"
    rf"|(?P<jenis>Undang-Undang|Peraturan Pemerintah Pengganti Undang-Undang|Peraturan Pemerintah|Peraturan Presiden)\s+Nomor\s+(?P<nomor>{_NUM})\s+Tahun\s+(?P<tahun>[\dOolIgS]{{4}})"
)
JENIS_ID = {"Undang-Undang": "uu", "Peraturan Pemerintah": "pp", "Peraturan Presiden": "perpres",
            "Peraturan Pemerintah Pengganti Undang-Undang": "perppu"}


def _num(s: str) -> str:
    return s.replace(" ", "").translate(OCR_DIGITS)


def law_id(m: re.Match) -> str:
    if m.group("uud"):
        return "uud-1945"
    if m.group("kuhap"):
        return "uu-1981-8"
    return f"{JENIS_ID[m.group('jenis')]}-{_num(m.group('tahun'))}-{_num(m.group('nomor'))}"


# ------------------------------------------------------------------ pasal references
RE_PASAL_REF = re.compile(r"\b[Pp]asal\.?\s+(\d{1,3}[A-Z]?)\b")
RE_AYAT_LIST = re.compile(r"^\s*(ayat\s*\(\d{1,2}[a-z]?\)(?:(?:\s*(?:,|dan|atau|sampai dengan))+\s*(?:ayat\s*)?\(\d{1,2}[a-z]?\))*)")
RE_RANGE = re.compile(r"^\s*sampai dengan\s+Pasal\s+(\d{1,3}[A-Z]?)")


def find_pasal_refs(text: str) -> list[dict]:
    """Every 'Pasal N [ayat (x)...] [sampai dengan Pasal M] [<law>]' mention.
    The law a reference belongs to is the first law citation that follows the reference
    *before* the next sentence/clause boundary; otherwise the containing act (resolved by caller)."""
    refs = []
    range_end = -1
    for m in RE_PASAL_REF.finditer(text):
        if m.start() < range_end:
            continue  # the "Pasal M" closing a "Pasal N sampai dengan Pasal M" range
        n = m.group(1)
        rest = text[m.end():]
        ayat = []
        ma = RE_AYAT_LIST.match(rest)
        if ma:
            ayat = re.findall(r"\((\d{1,2}[a-z]?)\)", ma.group(1))
        rng = RE_RANGE.match(rest)
        upto = rng.group(1) if rng else None
        if rng:
            range_end = m.end() + rng.end()
        # law that owns the reference: look ahead to the clause end
        clause = re.split(r"[;:]|\.\s|, (?:dan|serta) (?:setiap|pemerintah)|\bdipidana\b", rest, maxsplit=1)[0][:220]
        lm = RE_LAW.search(clause)
        between = clause[: lm.start()] if lm else ""
        law = None
        if lm and not re.search(r"\b(dalam|pada|oleh|terhadap|dengan)\s+(Undang-Undang|Peraturan)", between[-40:]) \
                and len(re.findall(r"\b[Pp]asal\b", between)) <= 12 and not re.search(r"\bUndang-Undang ini\b", between):
            law = law_id(lm)
        if re.match(r"^[^.;]{0,40}?Undang-Undang ini", rest):
            law = None
        refs.append({"pasal": n, "ayat": ayat, "sampai": upto, "law": law, "start": m.start(),
                     "kutipan": text[max(0, m.start() - 60): m.end() + 80]})
    return refs


def expand_range(a: str, b: str) -> list[str]:
    ka, kb = pasal_key(a), pasal_key(b)
    if ka[1] or kb[1] or kb[0] <= ka[0] or kb[0] - ka[0] > 60:
        return [a, b]
    return [str(i) for i in range(ka[0], kb[0] + 1)]


RE_DELEGASI = re.compile(
    r"diatur\s+(dengan|dalam)\s+(Peraturan Pemerintah|Peraturan Presiden|Peraturan Menteri|Peraturan Daerah|Undang-Undang)(?!\s+Nomor)"
)
DELEGASI_ID = {"Peraturan Pemerintah": "delegasi:PP", "Peraturan Presiden": "delegasi:Perpres",
               "Peraturan Menteri": "delegasi:Permen", "Peraturan Daerah": "delegasi:Perda",
               "Undang-Undang": "delegasi:UU"}


# ------------------------------------------------------------------ units of a pasal
def iter_units(p: dict, prefix: str = "") -> Iterable[tuple[str, str]]:
    """(ayat label or '', own text) for the pasal intro and each descendant unit, keeping the
    *top-level ayat* as location (huruf/angka text is attributed to their ayat)."""
    if p.get("teks"):
        yield prefix, p["teks"]
    for c in p.get("children", []):
        loc = prefix or (f"({c['nomor']})" if c["type"] == "ayat" else "")
        yield loc, c["teks"]
        for sub in c.get("children", []):
            yield from iter_units({"teks": sub["teks"], "children": sub.get("children", [])}, loc)


def pasal_internal_relations(src_version: str, per_of_text: str, p: dict, halaman: Any,
                             self_law: str = CONSOLIDATED) -> list[dict]:
    """merujuk + mendelegasikan found inside one pasal version's text."""
    out = []
    own = p["nomor"]
    for loc, txt in iter_units(p):
        for r in find_pasal_refs(txt):
            law = r["law"] or self_law
            targets = expand_range(r["pasal"], r["sampai"]) if r["sampai"] else [r["pasal"]]
            for t in targets:
                if law == self_law and t == own:
                    continue  # self-reference, not a relation
                out.append(edge(src_version, pasal_id(law, t), "merujuk",
                                "R-merujuk-range" if r["sampai"] else ("R-merujuk-eksternal" if r["law"] else "R-merujuk"),
                                r["kutipan"], peraturan=per_of_text, pasal=own, ayat_sumber=loc or None,
                                ayat_target=",".join(r["ayat"]) or None, halaman=halaman))
        for m in RE_DELEGASI.finditer(txt):
            out.append(edge(src_version, DELEGASI_ID[m.group(2)], "mendelegasikan", "R-delegasi",
                            txt[max(0, m.start() - 120): m.end() + 10], peraturan=per_of_text, pasal=own,
                            ayat_sumber=loc or None, halaman=halaman))
    return out


# ------------------------------------------------------------------ amendment relations
RE_AYAT_IN_INSTR = re.compile(r"ayat\s*\((\d{1,2}[a-z]?)\)")
_AYAT_SEQ = r"((?:ayat\s*\(\w+\)(?:\s*,|\s+dan|\s)*)+)"


def instruction_detail(instr: str) -> dict:
    """Which ayat a butir changes / inserts, read clause by clause. The ayat named in
    'di antara ayat (2b) dan ayat (3)' are insertion anchors, NOT changed ayat."""
    changed, inserted, pen = [], [], []
    for m in re.finditer(rf"[Kk]etentuan\s+{_AYAT_SEQ}[Pp]asal\s+\w+(?:\s+serta\s+penjelasan[^;]*?)?\s+diubah", instr):
        changed += RE_AYAT_IN_INSTR.findall(m.group(1))
    for m in re.finditer(r"(?:disisipkan|ditambah\w*)\s+\d+\s*\(\w+\)\s*(?:ayat|angka|huruf),?\s+yakni\s+(.*?)(?=\s+sehingga|;|,\s*(?:ketentuan|dan penjelasan|serta|dar\b|dan ketentuan))", instr):
        seg = m.group(1)
        inserted += re.findall(r"\((\w{1,3})\)", seg) + re.findall(r"(?:angka|huruf)\s+(\w{1,3})\b", seg)
    for m in re.finditer(rf"penjelasan\s+{_AYAT_SEQ}", instr):
        pen += RE_AYAT_IN_INSTR.findall(m.group(1))
    def j(xs: list[str]) -> str | None:
        return ",".join(dict.fromkeys(xs)) or None

    return {"ayat_diubah": j(changed), "unit_disisipkan": j(inserted), "penjelasan_ayat": j(pen)}


def amendment_relations(doc: dict) -> list[dict]:
    per = doc["id"]
    out = []
    roman = {r["nomor"]: r for r in doc["batang_tubuh"] if r["type"] == "pasal_romawi"}
    pembuka = roman.get("I", {}).get("teks", "")
    lm = RE_LAW.search(pembuka)
    if lm:
        out.append(edge(per, law_id(lm), "mengubah", "R-mengubah-peraturan", pembuka[:300], peraturan=per, lokasi="Pasal I",
                        halaman=roman["I"].get("halaman")))
    for b in roman.get("I", {}).get("children", []):
        instr = b.get("instruksi", "")
        loc = dict(peraturan=per, butir=b["nomor"], halaman=b.get("halaman"))
        content = {c["nomor"] for c in b["children"] if c["type"] == "pasal"}
        if "menyisipkan_pasal" in b.get("aksi", []):
            for n in b.get("pasal_baru", []):
                out.append(edge(per, pasal_id(CONSOLIDATED, n), "menyisipkan", "R-sisip-pasal", instr,
                                sisip_antara=",".join(b.get("sisip_antara", [])), teks_dimuat=n in content, **loc))
        detail = instruction_detail(instr)
        for n in b.get("pasal_target", []):
            if {"mengubah", "menambah_bagian_pasal", "menyisipkan_bagian_pasal"} & set(b.get("aksi", [])):
                if n in content:
                    out.append(edge(per, pasal_id(CONSOLIDATED, n), "mengubah", "R-ubah-pasal", instr, bagian="isi",
                                    ayat_diubah=detail["ayat_diubah"], unit_disisipkan=detail["unit_disisipkan"], **loc))
            if "mengubah_penjelasan" in b.get("aksi", []) or re.search(r"penjelasan\s+(?:ayat|Pasal)", instr):
                out.append(edge(per, pasal_id(CONSOLIDATED, n), "mengubah", "R-ubah-penjelasan", instr, bagian="penjelasan",
                                ayat_diubah=detail["penjelasan_ayat"], **loc))
        if "menghapus" in b.get("aksi", []):
            for n in re.findall(r"Pasal (\d+[A-Z]?) dihapus", instr):
                out.append(edge(per, pasal_id(CONSOLIDATED, n), "menghapus", "R-hapus", instr, **loc))
    # Pasal II: conditional end of validity, repeal clauses
    t2 = roman.get("II", {}).get("teks", "")
    if t2:
        for clause in re.split(r"(?<=\.)\s+(?=\d\s|[A-Z])", t2):
            m = re.search(r"berlaku sampai dengan diberlakukannya", clause)
            if m:
                lm = RE_LAW.search(clause[m.end():])
                cond = law_id(lm) if lm else None
                for r in find_pasal_refs(clause[: m.start()]):
                    out.append(edge(per, pasal_id(CONSOLIDATED, r["pasal"]), "membatasi_keberlakuan", "R-batas-berlaku",
                                    r["kutipan"] + " … " + clause[m.start(): m.start() + 160], peraturan=per, lokasi="Pasal II",
                                    ayat_target=",".join(r["ayat"]) or None, sampai_berlakunya=cond, halaman=roman["II"].get("halaman")))
            for m in re.finditer(r"dicabut dan dinyatakan tidak berlaku", clause):
                lms = list(RE_LAW.finditer(clause[: m.start()]))
                if lms:
                    out.append(edge(per, law_id(lms[-1]), "mencabut", "R-cabut", clause[: m.end()], peraturan=per, lokasi="Pasal II"))
    return out


def dasar_hukum_relations(doc: dict) -> list[dict]:
    per = doc["id"]
    m = doc["konsiderans"]["mengingat"]
    items = [c["teks"] for c in m["children"]] or [m["teks"]]
    out = []
    for txt in items:
        for lm in RE_LAW.finditer(txt):
            lid = law_id(lm)
            if lid == per or any(e["target"] == lid for e in out):
                continue
            # pasal of that law listed right before it (UUD 1945 articles)
            pasal = [r["pasal"] for r in find_pasal_refs(txt[: lm.start()])] if lid == "uud-1945" else []
            # every law in the item counts, incl. "sebagaimana telah diubah dengan UU 19/2016"
            out.append(edge(per, lid, "dasar_hukum", "R-dasar-hukum", txt[:300], peraturan=per, lokasi="Mengingat",
                            pasal_dirujuk=",".join(pasal) or None))
    return out
