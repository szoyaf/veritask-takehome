"""Create the manual-check sheet for relation precision/recall.

usage: python eval/make_relation_gt.py      (refuses to overwrite an existing sheet)

Writes ground_truth/relasi/relasi_gt.csv with every predicted relation inside a fixed SCOPE.
A human then:
  - sets label = benar | salah for every row (check kutipan + target + ayat against the PDF),
  - for anything in scope the pipeline MISSED, adds a row with label = terlewat.
Precision = benar / (benar + salah);  Recall = benar / (benar + terlewat), per relation type.
The scope is fixed in advance (not chosen after seeing errors) so recall is meaningful.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ground_truth" / "relasi" / "relasi_gt.csv"
G = json.loads((ROOT / "data/output/graph/graph.json").read_text(encoding="utf-8"))

STRUCTURAL = {"menetapkan_versi", "versi_dari", "menggantikan", "memuat"}
# merujuk / mendelegasikan are checked in these pasal versions only (whole text of each)
REF_SCOPE = {
    "uu-2008-11#pasal-5@uu-2008-11", "uu-2008-11#pasal-31@uu-2008-11", "uu-2008-11#pasal-36@uu-2008-11",
    "uu-2008-11#pasal-43@uu-2008-11", "uu-2008-11#pasal-52@uu-2008-11", "uu-2008-11#pasal-45@uu-2024-1",
}
COLS = ["id", "cakupan", "relasi", "source", "target", "ayat_sumber", "ayat_target", "detail", "aturan", "halaman",
        "kutipan", "label", "catatan"]


def scope_of(e: dict) -> str | None:
    r = e["relasi"]
    if r in STRUCTURAL:
        return None
    if r in ("mengubah", "menyisipkan", "menghapus", "mencabut"):
        return "S1 instruksi perubahan (Pasal I UU 2016 & UU 2024)"
    if r == "membatasi_keberlakuan":
        return "S2 Pasal II UU 2024"
    if r == "dasar_hukum":
        return "S3 Mengingat (3 UU)"
    if r in ("merujuk", "mendelegasikan") and e["source"] in REF_SCOPE:
        return "S4 rujukan & delegasi di 6 versi pasal"
    return None


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} sudah ada — tidak ditimpa (hapus manual bila ingin membuat ulang).")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    ranges: dict[tuple, dict] = {}
    for e in G["edges"]:
        s = scope_of(e)
        if not s:
            continue
        if e["aturan"].startswith("R-merujuk-range"):
            # one row per "Pasal N sampai dengan Pasal M" mention, not per expanded edge
            k = (e["source"], e["kutipan"], e.get("ayat_sumber"))
            if k in ranges:
                r = ranges[k]
                r["_targets"].append(e["target"].split("#pasal-")[1])
                r["target"] = f"{e['target'].split('#')[0]}#pasal-{r['_targets'][0]}..{r['_targets'][-1]} ({len(r['_targets'])} edge)"
                continue
        detail = "; ".join(f"{k}={e[k]}" for k in ("bagian", "ayat_diubah", "unit_disisipkan", "sisip_antara", "sampai_berlakunya",
                                                    "tanggal_akhir", "pasal_dirujuk", "target_ocr", "ayat_target_ocr") if e.get(k))
        row = {"cakupan": s, "relasi": e["relasi"], "source": e["source"], "target": e["target"],
               "ayat_sumber": e.get("ayat_sumber", ""), "ayat_target": e.get("ayat_target", ""), "detail": detail,
               "aturan": e["aturan"], "halaman": e.get("halaman", ""), "kutipan": e["kutipan"], "label": "", "catatan": ""}
        if e["aturan"].startswith("R-merujuk-range"):
            row["_targets"] = [e["target"].split("#pasal-")[1]]
            ranges[(e["source"], e["kutipan"], e.get("ayat_sumber"))] = row
        rows.append(row)
    for r in rows:
        r.pop("_targets", None)
    rows.sort(key=lambda r: (r["cakupan"], r["source"], r["relasi"], r["target"]))
    for i, r in enumerate(rows, 1):
        r["id"] = f"R{i:03d}"
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} relasi ditulis ke {OUT.relative_to(ROOT)}")
    print(Counter(r["cakupan"] for r in rows))
    print(Counter(r["relasi"] for r in rows))


if __name__ == "__main__":
    main()
