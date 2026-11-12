"""Evaluate Bagian 1 (extraction) against the manual ground truth.

usage:
  python eval/evaluate_extraction.py                       # verified GT only (the real numbers)
  python eval/evaluate_extraction.py --include-unverified  # dev dry-run; results marked DRAFT

Reads predictions from data/interim/<peraturan>.<method>.json (run the pipeline with
--all-methods first). Writes eval/results/extraction_metrics.{json,md}.

Metrics, per extraction method:
  CER          character error rate of the pasal text (jiwer), canonical form
               "(1) teks (2) teks a. teks ..." on both sides, whitespace collapsed, case and
               punctuation kept. Reported on found pasal, and with missing pasal counted as CER=1.
  Struktur     each GT unit (ayat / huruf / angka) is identified by its path, e.g. "(2)/c/1".
               A predicted unit is correct when the same path exists AND its own text has
               CER <= 0.10 against the GT unit (so a right label on the wrong text is wrong).
               precision = correct / predicted units, recall = correct / GT units.
               Plus "induk" accuracy: pasal placed under the right BAB/Bagian (UU induk only).
  Inventaris   missing / extra / duplicated pasal vs ground_truth/pasal_inventory.json.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import jiwer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from veritask.parse import iter_pasal  # noqa: E402

GT_DIR = ROOT / "ground_truth" / "pasal"
INV = ROOT / "ground_truth" / "pasal_inventory.json"
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "eval" / "results"
METHODS = ("pdfplumber", "pymupdf", "tesseract")
UNIT_CER_OK = 0.10
MARK = re.compile(r"^(\((\d{1,2}[a-z]?)\)|([a-z])\.|(\d{1,2}[a-z]?)\.)\s+(.*)$")


def ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def cer(ref: str, hyp: str) -> float:
    ref, hyp = ws(ref), ws(hyp)
    if not ref:
        return 0.0 if not hyp else 1.0
    return min(1.0, jiwer.cer(ref, hyp))


# ------------------------------------------------------------------ ground truth
def load_gt(path: Path) -> dict:
    meta, units, intro = {}, [], []
    stack: list[tuple[int, str]] = []  # (indent, path)
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("#"):
            k, _, v = raw[1:].partition(":")
            meta[k.strip()] = v.strip()
            continue
        if not raw.strip():
            continue
        indent = (len(raw) - len(raw.lstrip(" "))) // 2
        line = raw.strip()
        m = MARK.match(line)
        if not m:
            if units:
                units[-1]["teks"] = ws(units[-1]["teks"] + " " + line)
            else:
                intro.append(line)
            continue
        label = f"({m.group(2)})" if m.group(2) else (m.group(3) or m.group(4))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        p = (stack[-1][1] + "/" if stack else "") + label
        stack.append((indent, p))
        units.append({"path": p, "marker": m.group(1), "teks": m.group(5)})
    full = ws(" ".join(intro + [f"{u['marker']} {u['teks']}" for u in units]))
    return {"meta": meta, "units": units, "teks": full, "file": path.name}


# ------------------------------------------------------------------ predictions
def pred_units(n: dict, prefix: str = "") -> list[dict]:
    out = []
    for c in n["children"]:
        label = f"({c['nomor']})" if c["type"] == "ayat" else c["nomor"]
        marker = f"({c['nomor']})" if c["type"] == "ayat" else f"{c['nomor']}."
        p = prefix + label
        out.append({"path": p, "marker": marker, "teks": c["teks"]})
        out += pred_units(c, p + "/")
    return out


def pred_index(doc: dict) -> dict:
    idx = {}
    for p, anc in iter_pasal(doc["batang_tubuh"]):
        butir = next((a["nomor"] for a in anc if a["type"] == "butir"), "-")
        induk = " > ".join(
            f"{a['type'].upper() if a['type'] == 'bab' else a['type'].capitalize()} {a['nomor']}"
            for a in anc if a["type"] in ("bab", "bagian", "paragraf")
        ) or "-"
        units = pred_units(p)
        full = ws(" ".join(([p["teks"]] if p["teks"] else []) + [f"{u['marker']} {u['teks']}" for u in units]))
        idx.setdefault((butir, p["nomor"]), []).append({"units": units, "teks": full, "induk": induk})
    return idx


def first_diffs(ref: str, hyp: str, n: int = 3, ctx: int = 25) -> list[str]:
    ref, hyp = ws(ref), ws(hyp)
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        out.append(f"{op}: GT «…{ref[max(0, i1 - ctx):i1]}[{ref[i1:i2]}]{ref[i2:i2 + ctx]}…» vs PRED «[{hyp[j1:j2]}]»")
        if len(out) >= n:
            break
    return out


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-unverified", action="store_true")
    args = ap.parse_args(argv)

    gts = [load_gt(p) for p in sorted(GT_DIR.glob("*.txt"))]
    n_unverified = sum(1 for g in gts if g["meta"].get("verified", "no").lower() != "yes")
    if not args.include_unverified:
        gts = [g for g in gts if g["meta"].get("verified", "no").lower() == "yes"]
    draft = args.include_unverified and n_unverified > 0
    inventory = json.loads(INV.read_text(encoding="utf-8"))

    results = {"draft": draft, "gt_files": len(gts), "gt_unverified_total": n_unverified, "methods": {}}
    for method in METHODS:
        preds = {}
        for per in ("uu-2008-11", "uu-2016-19", "uu-2024-1"):
            f = INTERIM / f"{per}.{method}.json"
            if f.exists():
                preds[per] = pred_index(json.loads(f.read_text(encoding="utf-8")))
        if not preds:
            continue
        rows, unit_gt = [], 0
        unit_pred = unit_ok = 0
        induk_n = induk_ok = 0
        for g in gts:
            per, butir, nomor = g["meta"]["peraturan"], g["meta"]["butir"], g["meta"]["pasal"]
            cands = preds.get(per, {}).get((butir, nomor), [])
            unit_gt += len(g["units"])
            if not cands:
                rows.append({"file": g["file"], "found": False, "cer": 1.0, "units_ok": 0, "units_gt": len(g["units"])})
                continue
            p = cands[0]
            c = cer(g["teks"], p["teks"])
            pu = {u["path"]: u for u in p["units"]}
            ok = sum(1 for u in g["units"] if u["path"] in pu and cer(u["teks"], pu[u["path"]]["teks"]) <= UNIT_CER_OK)
            unit_pred += len(p["units"])
            unit_ok += ok
            if per == "uu-2008-11":
                induk_n += 1
                induk_ok += int(p["induk"] == g["meta"].get("induk"))
            rows.append({
                "file": g["file"], "found": True, "cer": round(c, 4), "units_ok": ok, "units_gt": len(g["units"]),
                "units_pred": len(p["units"]), "induk_pred": p["induk"], "induk_gt": g["meta"].get("induk"),
                "diffs": first_diffs(g["teks"], p["teks"]) if c > 0 else [],
            })
        found = [r for r in rows if r["found"]]
        # inventory
        inv = {}
        for per, spec in inventory.items():
            if per.startswith("_") or per not in preds:
                continue
            expected = [x if ":" in x else f"-:{x}" for x in spec["pasal"]]
            got = []
            for (butir, nomor), lst in preds[per].items():
                got += [f"{butir}:{nomor}"] * len(lst)
            cnt = Counter(got)
            inv[per] = {
                "verified": spec["verified"],
                "expected": len(expected),
                "found": len(set(got) & set(expected)),
                "missing": sorted(set(expected) - set(got)),
                "extra": sorted(set(got) - set(expected)),
                "duplicated": sorted(k for k, v in cnt.items() if v > 1),
            }
        results["methods"][method] = {
            "pasal_dievaluasi": len(rows),
            "pasal_ditemukan": len(found),
            "cer_mean_found": round(sum(r["cer"] for r in found) / max(1, len(found)), 4),
            "cer_mean_incl_missing": round(sum(r["cer"] for r in rows) / max(1, len(rows)), 4),
            "struktur_recall": round(unit_ok / max(1, unit_gt), 4),
            "struktur_precision": round(unit_ok / max(1, unit_pred), 4),
            "induk_accuracy": round(induk_ok / induk_n, 4) if induk_n else None,
            "inventaris": inv,
            "per_pasal": rows,
        }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extraction_metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    md = render_md(results)
    (OUT / "extraction_metrics.md").write_text(md, encoding="utf-8")
    print(md)


def render_md(r: dict) -> str:
    L = []
    if r["draft"]:
        L.append("> **DRAFT** — includes UNVERIFIED ground truth pre-filled from pdfplumber output. "
                 "pdfplumber numbers are trivially ~0 here and MUST NOT be reported.\n")
    L.append(f"Ground truth files used: {r['gt_files']} (unverified remaining: {r['gt_unverified_total']})\n")
    L.append("| Metode | Pasal ditemukan | CER (ditemukan) | CER (incl. hilang=1) | Struktur P | Struktur R | Induk benar |")
    L.append("|---|---|---|---|---|---|---|")
    for m, x in r["methods"].items():
        induk = "-" if x["induk_accuracy"] is None else f"{x['induk_accuracy']:.0%}"
        L.append(f"| {m} | {x['pasal_ditemukan']}/{x['pasal_dievaluasi']} | {x['cer_mean_found']:.2%} | {x['cer_mean_incl_missing']:.2%} | "
                 f"{x['struktur_precision']:.2%} | {x['struktur_recall']:.2%} | {induk} |")
    L.append("\n### Inventaris pasal (hilang / ekstra / duplikat)")
    for m, x in r["methods"].items():
        for per, v in x["inventaris"].items():
            L.append(f"- {m} · {per}{'' if v['verified'] else ' (inventaris belum diverifikasi)'}: "
                     f"{v['found']}/{v['expected']} ditemukan; hilang={v['missing'] or '-'}; ekstra={v['extra'] or '-'}; duplikat={v['duplicated'] or '-'}")
    L.append("\n### Per pasal")
    for m, x in r["methods"].items():
        L.append(f"\n**{m}**\n\n| GT file | CER | unit benar | catatan |\n|---|---|---|---|")
        for row in x["per_pasal"]:
            note = "TIDAK DITEMUKAN" if not row["found"] else ("; ".join(row["diffs"][:2]).replace("|", "/")[:220])
            L.append(f"| {row['file']} | {row['cer']:.2%} | {row['units_ok']}/{row['units_gt']} | {note} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
