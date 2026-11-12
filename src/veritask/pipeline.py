"""One-command pipeline:  python run.py [--method pdfplumber|pymupdf|tesseract] [--all-methods] [--as-of YYYY-MM-DD]

Stages and outputs
  1. PDF -> cleaned lines -> structured JSON   data/output/structured/<id>.json
     (every method run, for eval/evaluate_extraction.py: data/interim/<id>.<method>.{json,raw.txt,clean.txt})
  2. relations + pasal versions -> graph        data/output/graph/
  3. metadata, validated by the Pydantic models data/output/metadata/
  4. RAG chunks                                 data/output/chunks/chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from . import chunks, metadata
from .clean import clean_pages
from .extract import extract_pages, tesseract_available
from .graph import build as build_graph
from .graph import export as export_graph
from .parse import iter_pasal, parse_document

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "data" / "sources.json"
EXTERNAL = ROOT / "data" / "external_facts.json"
OUT_STRUCT = ROOT / "data" / "output" / "structured"
INTERIM = ROOT / "data" / "interim"
OUT_GRAPH = ROOT / "data" / "output" / "graph"
OUT_META = ROOT / "data" / "output" / "metadata"
OUT_CHUNKS = ROOT / "data" / "output" / "chunks" / "chunks.jsonl"


def link_penjelasan(doc: dict) -> None:
    """Attach each Penjelasan entry to the pasal it explains (by number; for amending acts
    by butir number + pasal number). Entries with no matching pasal are kept and flagged."""
    pen = doc.get("penjelasan")
    if not pen:
        return
    pasal_index = {}
    for p, anc in iter_pasal(doc["batang_tubuh"]):
        butir = next((a["nomor"] for a in anc if a["type"] == "butir"), None)
        pasal_index[(butir, p["nomor"])] = p
        pasal_index.setdefault((None, p["nomor"]), p)
    for e in pen["pasal_demi_pasal"]:
        if e.get("pasal_romawi"):
            continue
        target = pasal_index.get((e.get("butir"), e["nomor"])) or pasal_index.get((None, e["nomor"]))
        if target is None and e.get("butir") and re.match(r"\d+", e["nomor"]):
            # OCR-garbled heading ("168"): take the not-yet-explained pasal of the same butir
            # whose numeric root the heading starts with (16B)
            cands = [p for (b, _), p in pasal_index.items()
                     if b == e["butir"] and p["nomor"] != e["nomor"] and "penjelasan" not in p
                     and e["nomor"].startswith(re.match(r"\d+", p["nomor"]).group(0))]
            if cands:
                target = cands[-1]
                e["nomor_ocr"], e["nomor"] = e["nomor"], target["nomor"]
        if target is not None:
            target["penjelasan"] = {"teks": e["teks_lengkap"], "children": e["children"]}
            e["menjelaskan"] = target["nomor"]
        else:
            e["menjelaskan"] = None  # e.g. "Penjelasan Pasal 15 diubah" with no new pasal text


def run_one(src: dict, method: str) -> dict:
    pages = extract_pages(ROOT / src["file"], method)
    lines = clean_pages(pages)
    # text dumps for inspection: raw text layer vs cleaned lines
    (INTERIM / f"{src['id']}.{method}.raw.txt").write_text(
        "".join(f"=====PAGE {i}=====\n{p}\n" for i, p in enumerate(pages, 1)), encoding="utf-8")
    (INTERIM / f"{src['id']}.{method}.clean.txt").write_text(
        "".join(f"{l.page:>2}| {l.text}\n" for l in lines), encoding="utf-8")
    doc = parse_document(lines)
    link_penjelasan(doc)
    return {"id": src["id"], "metode_ekstraksi": method, "jumlah_halaman": len(pages), **doc}


def summary(doc: dict) -> str:
    pasal = list(iter_pasal(doc["batang_tubuh"]))
    nomor = [p["nomor"] for p, _ in pasal]
    with_pen = sum(1 for p, _ in pasal if "penjelasan" in p)
    return (f"{doc['id']:<11} {doc['metode_ekstraksi']:<10} pasal={len(nomor):>3} penjelasan_tertaut={with_pen:>3}  "
            f"[{', '.join(nomor[:6])} ... {', '.join(nomor[-3:])}]")


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="pdfplumber")
    ap.add_argument("--all-methods", action="store_true", help="also run the other extractors for comparison")
    ap.add_argument("--as-of", default=None, help="reference date (ISO) for derived status; default today")
    args = ap.parse_args(argv)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    OUT_STRUCT.mkdir(parents=True, exist_ok=True)
    INTERIM.mkdir(parents=True, exist_ok=True)
    methods = [args.method]
    if args.all_methods:
        methods += [m for m in ("pdfplumber", "pymupdf") if m != args.method]
        if tesseract_available():
            methods.append("tesseract")

    # Stage 1: extraction + structure
    docs = {}
    for src in sources:
        for m in methods:
            doc = run_one(src, m)
            doc["sumber"] = {k: src[k] for k in ("sumber_url", "detail_url", "tanggal_unduh", "hash_file")}
            _write_json(INTERIM / f"{src['id']}.{m}.json", doc)
            if m == args.method:
                _write_json(OUT_STRUCT / f"{src['id']}.json", doc)
                docs[src["id"]] = doc
            print(summary(doc))

    # Stage 2: relations, pasal versions, graph export
    ext = json.loads(EXTERNAL.read_text(encoding="utf-8"))
    g = build_graph(docs, ext, as_of=args.as_of)
    export_graph(g, OUT_GRAPH)
    print(f"graph (status per {g['as_of']}): {len(g['pasal'])} pasal, {sum(len(v) for v in g['versi'].values())} versi, "
          f"relasi={dict(Counter(e['relasi'] for e in g['edges']))}")

    # Stage 3: metadata (validated by the Pydantic models on construction)
    src_by_id = {s["id"]: s for s in sources}
    per_meta = metadata.build_peraturan(docs, g, src_by_id, ROOT)
    pasal_meta = metadata.build_pasal(g)
    metadata.export(per_meta, pasal_meta, OUT_META)
    print(f"metadata: {len(per_meta)} peraturan, {len(pasal_meta)} record pasal-versi (valid terhadap skema)")

    # Stage 4: RAG chunks
    ch = chunks.build_chunks([p.model_dump(mode="json") for p in per_meta],
                             [p.model_dump(mode="json") for p in pasal_meta], docs)
    chunks.export(ch, OUT_CHUNKS)
    over = [c["chunk_id"] for c in ch if c["token_est"] > chunks.MAX_TOKENS]
    print(f"chunks: {len(ch)} ({dict(Counter(c['jenis_chunk'] for c in ch))}); >{chunks.MAX_TOKENS} token: {over or 'tidak ada'}")


if __name__ == "__main__":
    main()
