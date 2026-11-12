"""Bagian 4 demo: example questions -> the chunks that SHOULD be retrieved, and a tiny
retriever (metadata filter + BM25, no embeddings) showing the chunk metadata is enough to
get the time-correct answer.

usage: python eval/rag_examples.py [--as-of 2026-11-08]

Retrieval logic
 1. parse the question: explicit 'Pasal N [ayat (m)]', time ('saat ini' -> as_of, 'tahun 2020' -> 2020-07-01)
 2. filter chunks valid on that date: berlaku_sejak <= t < berlaku_sampai (null = open)
    (default = currently valid only; historical versions are only reached by an explicit date)
 3. explicit pasal/ayat -> exact metadata match; otherwise BM25 over header+teks
 4. if an explicitly asked pasal/ayat has NO valid chunk on that date, say so and return the
    latest version that had it (with its validity) instead of silently answering with old text.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = [json.loads(l) for l in open(ROOT / "data/output/chunks/chunks.jsonl", encoding="utf-8")]

QUESTIONS = [
    {"q": "Apa bunyi Pasal 27 ayat (3) UU ITE yang berlaku saat ini?",
     "harap": [], "harap_fallback": "uu-2008-11#pasal-27@uu-2016-19::pasal",
     "catatan": "Jebakan versi: sejak UU 1/2024 Pasal 27 hanya 2 ayat; muatan penghinaan pindah ke Pasal 27A, "
                "yang menurut Pasal II UU 1/2024 berakhir saat KUHP berlaku (2026-01-02). Jawaban benar: tidak ada lagi."},
    {"q": "Bagaimana bunyi Pasal 27 ayat (3) UU ITE pada tahun 2020?",
     "harap": ["uu-2008-11#pasal-27@uu-2016-19::pasal"],
     "catatan": "Versi 2016 (teks 2008, penjelasan diubah 2016); penjelasan tertaut: ::penjelasan"},
    {"q": "Apa ancaman pidana bagi orang yang menyebarkan berita bohong yang mengakibatkan kerugian konsumen dalam Transaksi Elektronik?",
     "harap": ["uu-2008-11#pasal-45A@uu-2024-1::ayat-1", "uu-2008-11#pasal-28@uu-2024-1::ayat-1"],
     "catatan": "45A ayat (1) masih berlaku (Pasal II hanya membatasi ayat 2 dan 3)"},
    {"q": "Apa kewajiban Penyelenggara Sistem Elektronik dalam memberikan pelindungan bagi anak?",
     "harap": ["uu-2008-11#pasal-16A@uu-2024-1::pasal"], "catatan": "Pasal sisipan UU 1/2024"},
    {"q": "Ketentuan mana dalam UU ITE yang berlaku sampai dengan diberlakukannya Kitab Undang-Undang Hukum Pidana?",
     "harap": ["uu-2024-1::pasal-II"], "catatan": "Pasal II UU 1/2024 (chunk ketentuan_penutup)"},
    {"q": "Apa yang dimaksud dengan Penyelenggara Sistem Elektronik?",
     "harap": ["uu-2008-11#pasal-1@uu-2016-19::angka-6a"], "catatan": "Definisi disisipkan UU 19/2016 (angka 6a)"},
]

STOP = set("apa yang dan atau di ke dari dalam pada untuk dengan bagi ini itu adalah bagaimana bunyi uu ite saat kapan mana "
           "oleh sebagai tahun tentang orang setiap dimaksud".split())


def toks(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 1]


class BM25:
    def __init__(self, docs: list[str], k1=1.4, b=0.75):
        self.d = [Counter(toks(x)) for x in docs]
        self.len = [sum(c.values()) for c in self.d]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(t for c in self.d for t in c)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + .5) / (f + .5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def score(self, q: str, i: int) -> float:
        c, L = self.d[i], self.len[i]
        return sum(self.idf.get(t, 0) * c[t] * (self.k1 + 1) / (c[t] + self.k1 * (1 - self.b + self.b * L / self.avg)) for t in toks(q) if t in c)


def valid_on(c: dict, t: str) -> bool:
    return c["berlaku_sejak"] <= t and (c["berlaku_sampai"] is None or c["berlaku_sampai"] > t)


def parse(q: str, today: str) -> dict:
    m = re.search(r"Pasal (\d+[A-Z]?)(?: ayat \((\d+[a-z]?)\))?", q)
    y = re.search(r"tahun (\d{4})", q)
    return {"pasal": m.group(1) if m else None, "ayat": m.group(2) if m and m.group(2) else None,
            "tanggal": f"{y.group(1)}-07-01" if y and "Nomor" not in q[max(0, y.start() - 12): y.start()] else today}


def retrieve(q: str, today: str, k: int = 3) -> dict:
    p = parse(q, today)
    t = p["tanggal"]
    pasal_chunks = [c for c in CHUNKS if c["jenis_chunk"] in ("pasal", "ayat", "angka", "huruf")]
    if p["pasal"]:
        pid = f"uu-2008-11#pasal-{p['pasal']}"
        cands = [c for c in pasal_chunks if c["pasal_id"] == pid]
        def has_ayat(c):  # whole-pasal chunk contains "(m)" marker, or ayat chunk with that number
            return p["ayat"] is None or c["ayat"] == p["ayat"] or (c["ayat"] is None and f"({p['ayat']})" in c["teks"])
        hit = [c for c in cands if valid_on(c, t) and has_ayat(c)]
        if hit:
            return {"parse": p, "hasil": hit[:k], "fallback": None}
        hist = sorted([c for c in cands if has_ayat(c)], key=lambda c: c["berlaku_sejak"], reverse=True)
        return {"parse": p, "hasil": [], "fallback": hist[0] if hist else None,
                "versi_berlaku_pasal": [c["chunk_id"] for c in cands if valid_on(c, t)]}
    pool = [c for c in CHUNKS if valid_on(c, t) and c["status"] != "tidak_berlaku" and c["jenis_chunk"] != "penjelasan_umum"]
    if re.search(r"yang dimaksud dengan", q, re.I):
        # definition intent -> Ketentuan Umum (Pasal 1) first. Without this router BM25 ranks long
        # Penjelasan that repeat the term above the one-line definition (docs/catatan_teknis.md, bagian 4).
        p["router"] = "definisi"
        pool = [c for c in pool if c["pasal_id"] == "uu-2008-11#pasal-1" and c["jenis_chunk"] != "penjelasan_pasal"] or pool
    bm = BM25([c["teks_untuk_embedding"] for c in pool])
    ranked = sorted(range(len(pool)), key=lambda i: bm.score(q, i), reverse=True)
    return {"parse": p, "hasil": [pool[i] for i in ranked[:k]], "fallback": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=date.today().isoformat())
    a = ap.parse_args()
    lines, n_ok = [f"# Contoh retrieval (tanggal acuan {a.as_of}; filter metadata + BM25, tanpa embedding)\n"], 0
    for i, item in enumerate(QUESTIONS, 1):
        r = retrieve(item["q"], a.as_of)
        got = [c["chunk_id"] for c in r["hasil"]]
        if item["harap"]:
            ok = any(h in got for h in item["harap"])
        else:
            ok = not got and r["fallback"] and r["fallback"]["chunk_id"] == item["harap_fallback"]
        n_ok += ok
        lines.append(f"## Q{i}. {item['q']}\n")
        lines.append(f"- parse: {r['parse']}")
        lines.append(f"- diharapkan: {item['harap'] or 'TIDAK ADA chunk berlaku → fallback ' + item['harap_fallback']}")
        lines.append(f"- {'✅' if ok else '❌'} terambil (top-3): {got or '—'}")
        if r["fallback"]:
            f = r["fallback"]
            lines.append(f"- tidak ada versi berlaku pada {r['parse']['tanggal']}; versi terakhir yang memuatnya: "
                         f"`{f['chunk_id']}` (berlaku {f['berlaku_sejak']} s.d. {f['berlaku_sampai']}); "
                         f"versi pasal yang berlaku sekarang: {r.get('versi_berlaku_pasal')}")
        if r["hasil"]:
            c = r["hasil"][0]
            lines.append(f"- top-1 header: `{c['header']}`")
            lines.append(f"- top-1 teks: {c['teks'][:220]}…")
            if c.get("penjelasan_chunk_id"):
                lines.append(f"- penjelasan tertaut: `{c['penjelasan_chunk_id']}`")
        lines.append(f"- catatan: {item['catatan']}\n")
    lines.insert(1, f"**{n_ok}/{len(QUESTIONS)} pertanyaan mengambil chunk yang diharapkan.**\n")
    out = ROOT / "eval/results/rag_examples.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
