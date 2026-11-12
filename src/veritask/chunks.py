"""Bagian 4: chunks for RAG that follow legal units, not fixed token windows.

Rules
  * one chunk per pasal VERSION (all versions kept, with berlaku_sejak / berlaku_sampai,
    so "aturan pada tahun 2020" stays answerable; default retrieval filters on status).
  * split into one chunk per top-level unit (ayat; or angka/huruf when the pasal has no ayat) when
      - the pasal exceeds MAX_TOKENS, or
      - some ayat has a different validity than the rest (Pasal II UU 1/2024): then each ayat
        chunk carries its own status, so retrieval can drop exactly the ayat that ended.
  * every chunk starts with a context header:
      UU 11/2008 (ITE, diubah UU 1/2024) › BAB VII Perbuatan yang Dilarang › Pasal 27 ayat (2)
      [bunyi menurut UU 1/2024 · berlaku 2024-01-02 s.d. sekarang]
  * Penjelasan Pasal is a SEPARATE chunk linked by pasal_id/versi_id (+ penjelasan_chunk_id on the pasal
    chunk): keeps pasal embeddings focused on the norm, lets the answerer pull the official
    interpretation on demand, and drops "Cukup jelas." (no chunk) instead of polluting the index.
  * also: Konsiderans (Menimbang), Penjelasan Umum (per paragraph group), and the closing provisions
    of amending acts (Pasal II), because questions about effective dates live there.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

MAX_TOKENS = 512
CHARS_PER_TOKEN = 3.5  # conservative estimate for Indonesian legal text (measured tokenisers give ~3.8-4.2)


def est_tokens(s: str) -> int:
    return math.ceil(len(s) / CHARS_PER_TOKEN)


def _short(per: dict) -> str:
    return per["judul_singkat"]


def _doc_label(cons: dict, amenders: list[dict]) -> str:
    last = max(amenders, key=lambda p: p["tanggal_berlaku"]) if amenders else None
    return f"{_short(cons)} (ITE{', diubah ' + _short(last) if last else ''})"


def _status_ayat(v: dict, ayat_label: str) -> tuple[str, str | None]:
    """Status of one ayat chunk inside a version."""
    end = next((a["berlaku_sampai"] for a in v["ayat"] if f"({a['nomor']})" == ayat_label and a.get("berlaku_sampai")), None)
    if end and ayat_label in v["ayat_tidak_berlaku"]:
        return "tidak_berlaku", end
    if v["status"] == "berlaku_sebagian":
        return "berlaku", end or v["berlaku_sampai"]
    return v["status"], end or v["berlaku_sampai"]


def _mark(u: dict) -> str:
    return f"({u['nomor']})" if u["jenis"] == "ayat" else f"{u['nomor']}."


def _unit_text(u: dict) -> str:
    """Text of a unit with its marker and all its descendants: '(2) ... a. ... b. ...'."""
    return " ".join([f"{_mark(u)} {u['teks']}".strip()] + [_unit_text(c) for c in u.get("anak", [])])


def _pack(intro: str, parts: list[str], budget: int) -> list[str]:
    """Greedy-pack parts (each kept whole) into pieces of <= budget tokens, repeating the intro."""
    out, cur = [], []
    flat = []
    for p in parts:  # an item that alone exceeds the budget is cut at clause boundaries
        if est_tokens(f"{intro} {p}") > budget:
            flat += [s for s in re.split(r"(?<=[;:])\s+|(?<=\.)\s+(?=[A-Z(])", p) if s]
        else:
            flat.append(p)
    for p in flat:
        cand = " ".join([intro] + cur + [p]).strip()
        if cur and est_tokens(cand) > budget:
            out.append(" ".join([intro] + cur).strip())
            cur = [p]
        else:
            cur.append(p)
    if cur:
        out.append(" ".join([intro] + cur).strip())
    return out


def _split_unit(u: dict, budget: int) -> list[tuple[str, str]]:
    """(suffix, text) pieces of one top-level unit; a long ayat is split by its huruf/angka
    with the ayat's own sentence repeated so each piece is self-contained."""
    full = _unit_text(u)
    if est_tokens(full) <= budget or not u.get("anak"):
        return [("", full)]
    intro = f"{_mark(u)} {u['teks']}".strip()
    pieces = _pack(intro, [_unit_text(c) for c in u["anak"]], budget)
    return [(f"-bag{i + 1}", p) for i, p in enumerate(pieces)]


def build_chunks(peraturan: list[dict], pasal: list[dict], docs: dict) -> list[dict]:
    per = {p["id"]: p for p in peraturan}
    cons = per["uu-2008-11"]
    amenders = [p for p in peraturan if p["jenis_struktur"] == "perubahan"]
    label = _doc_label(cons, amenders)
    chunks: list[dict] = []

    def base(v: dict) -> dict:
        return {"peraturan_id": v["peraturan_id"], "pasal_id": v["pasal_id"], "versi_id": v["versi_id"],
                "ditetapkan_oleh": v["ditetapkan_oleh"], "berlaku_sejak": v["berlaku_sejak"],
                "bidang": [b["label"] for b in v["bidang"]], "halaman": v["halaman"],
                "sumber_url": per[v["ditetapkan_oleh"]]["sumber_url"]}

    for v in pasal:
        if v["jenis_perubahan"] == "dihapus":
            continue
        path = " › ".join(x for x in (label, v["bab"], v["bagian"], v["paragraf"]) if x)
        ver = f"[bunyi menurut {_short(per[v['ditetapkan_oleh']])} · berlaku {v['berlaku_sejak']} s.d. {v['berlaku_sampai'] or 'sekarang'}]"
        pen_id = None
        pen = v.get("penjelasan")
        if pen and not re.fullmatch(r"\s*Cukup jelas\.?\s*", pen["teks"]):
            pen_id = f"{v['versi_id']}::penjelasan"
            head = f"{path} › Penjelasan Pasal {v['nomor']} [penjelasan menurut {_short(per[pen['sumber_peraturan']])}]"
            budget = MAX_TOKENS - est_tokens(head) - 2
            parts = re.split(r"\s(?=(?:Ayat \(\d+[a-z]?\)|Huruf [a-z]|Angka \d+[a-z]?)\s)", pen["teks"])
            pieces = [pen["teks"]] if est_tokens(pen["teks"]) <= budget else _pack("", parts, budget)
            for i, piece in enumerate(pieces):
                chunks.append({"chunk_id": pen_id + (f"-bag{i + 1}" if len(pieces) > 1 else ""), "jenis_chunk": "penjelasan_pasal",
                               **base(v), "ayat": None, "status": v["status"], "berlaku_sampai": v["berlaku_sampai"],
                               "header": head + (f" (bagian {i + 1}/{len(pieces)})" if len(pieces) > 1 else ""),
                               "teks": piece, "menjelaskan_pasal": v["versi_id"]})
        whole = f"{path} › Pasal {v['nomor']} {ver}\n{v['teks']}"
        must_split = est_tokens(whole) > MAX_TOKENS or any(a.get("berlaku_sampai") for a in v["ayat"])
        if not must_split or not v["ayat"]:
            chunks.append({"chunk_id": f"{v['versi_id']}::pasal", "jenis_chunk": "pasal", **base(v), "ayat": None,
                           "status": v["status"], "berlaku_sampai": v["berlaku_sampai"],
                           "header": f"{path} › Pasal {v['nomor']} {ver}", "teks": v["teks"],
                           "penjelasan_chunk_id": pen_id})
            continue
        # split per top-level unit; intro text (before the first marker) is repeated as context
        intro = v["teks"].split(_unit_text(v["ayat"][0])[:30])[0].strip() if v["ayat"] else ""
        for u in v["ayat"]:
            lab = f"({u['nomor']})" if u["jenis"] == "ayat" else (f"angka {u['nomor']}" if u["jenis"] == "angka" else f"huruf {u['nomor']}")
            st, end = _status_ayat(v, lab) if u["jenis"] == "ayat" else (("berlaku" if v["status"] == "berlaku_sebagian" else v["status"]), v["berlaku_sampai"])
            ver_u = f"[bunyi menurut {_short(per[v['ditetapkan_oleh']])} · berlaku {v['berlaku_sejak']} s.d. {end or 'sekarang'}]"
            ref = f"Pasal {v['nomor']} ayat {lab}" if u["jenis"] == "ayat" else f"Pasal {v['nomor']} {lab}"
            header = f"{path} › {ref} {ver_u}"
            budget = MAX_TOKENS - est_tokens(header + " " + intro) - 2
            for suffix, piece in _split_unit(u, budget):
                body = (intro + " " if intro else "") + piece
                chunks.append({"chunk_id": f"{v['versi_id']}::{u['jenis']}-{u['nomor']}{suffix}", "jenis_chunk": u["jenis"], **base(v),
                               "ayat": u["nomor"], "status": st, "berlaku_sampai": end,
                               "header": header + (f" (bagian {suffix[4:]})" if suffix else ""), "teks": body.strip(),
                               "penjelasan_chunk_id": pen_id})

    # -------- non-pasal chunks per regulation
    for pid, d in docs.items():
        p = per[pid]
        common = {"peraturan_id": pid, "pasal_id": None, "versi_id": None, "ditetapkan_oleh": pid, "ayat": None,
                  "berlaku_sejak": p["tanggal_berlaku"], "berlaku_sampai": None, "status": "berlaku",
                  "bidang": [b["label"] for b in p["bidang"]], "sumber_url": p["sumber_url"]}
        men = d["konsiderans"]["menimbang"]
        txt = " ".join(f"{c['nomor']}. {c['teks']}" for c in men["children"]) or men["teks"]
        chunks.append({"chunk_id": f"{pid}::konsiderans", "jenis_chunk": "konsiderans", **common, "halaman": 1,
                       "header": f"{_short(p)} tentang {p['tentang']} › Konsiderans (Menimbang)", "teks": txt})
        for r in d["batang_tubuh"]:
            if r["type"] == "pasal_romawi" and r["nomor"] == "II":
                chunks.append({"chunk_id": f"{pid}::pasal-II", "jenis_chunk": "ketentuan_penutup", **common, "halaman": r.get("halaman"),
                               "header": f"{_short(p)} ({p['judul']}) › Pasal II (ketentuan keberlakuan)", "teks": r["teks"]})
        umum = (d.get("penjelasan") or {}).get("umum", "")
        for i, part in enumerate(_pack_paragraphs(umum)):
            chunks.append({"chunk_id": f"{pid}::penjelasan-umum-{i + 1}", "jenis_chunk": "penjelasan_umum", **common, "halaman": None,
                           "header": f"{_short(p)} tentang {p['tentang']} › Penjelasan Umum (bagian {i + 1})", "teks": part})
    for c in chunks:
        c["teks_untuk_embedding"] = f"{c['header']}\n{c['teks']}"
        c["token_est"] = est_tokens(c["teks_untuk_embedding"])
    return chunks


def _pack_paragraphs(text: str) -> list[str]:
    """Penjelasan Umum has no inner structure: pack sentences into <= MAX_TOKENS pieces."""
    if not text:
        return []
    sents = re.split(r"(?<=\.)\s+(?=[A-Z])", text)
    out, cur = [], ""
    for s in sents:
        if cur and est_tokens(cur + " " + s) > MAX_TOKENS - 40:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def export(chunks: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
