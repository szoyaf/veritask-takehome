"""Relation precision / recall from the manually labelled sheet.

usage: python eval/evaluate_relations.py
Reads ground_truth/relasi/relasi_gt.csv (label: benar | salah | terlewat; empty = not checked yet)
Writes eval/results/relation_metrics.md
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "ground_truth" / "relasi" / "relasi_gt.csv"
OUT = ROOT / "eval" / "results" / "relation_metrics.md"


def main():
    rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
    unlabeled = [r for r in rows if not r["label"].strip()]
    bad_label = [r for r in rows if r["label"].strip() and r["label"].strip().lower() not in ("benar", "salah", "terlewat")]
    by = defaultdict(lambda: {"benar": 0, "salah": 0, "terlewat": 0})
    for r in rows:
        lab = r["label"].strip().lower()
        if lab in ("benar", "salah", "terlewat"):
            by[r["relasi"]][lab] += 1
            by["SEMUA"][lab] += 1
    L = [f"Relasi di sheet: {len(rows)} | sudah dilabel: {len(rows) - len(unlabeled)} | belum: {len(unlabeled)}"
         + (f" | label tidak dikenal: {[r['id'] for r in bad_label]}" if bad_label else ""), ""]
    if unlabeled:
        L.append("> Belum semua baris dilabel — angka di bawah hanya untuk baris yang sudah dicek.\n")
    L += ["| Relasi | benar | salah | terlewat | Presisi | Recall |", "|---|---|---|---|---|---|"]
    for rel in sorted(by, key=lambda k: (k == "SEMUA", k)):
        c = by[rel]
        p = c["benar"] / (c["benar"] + c["salah"]) if c["benar"] + c["salah"] else float("nan")
        rc = c["benar"] / (c["benar"] + c["terlewat"]) if c["benar"] + c["terlewat"] else float("nan")
        L.append(f"| {'**SEMUA**' if rel == 'SEMUA' else rel} | {c['benar']} | {c['salah']} | {c['terlewat']} | {p:.1%} | {rc:.1%} |")
    wrong = [r for r in rows if r["label"].strip().lower() in ("salah", "terlewat")]
    if wrong:
        L += ["", "### Relasi salah / terlewat", "", "| id | label | relasi | source → target | catatan |", "|---|---|---|---|---|"]
        for r in wrong:
            L.append(f"| {r['id']} | {r['label']} | {r['relasi']} | {r['source']} → {r['target']} | {r['catatan']} |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
