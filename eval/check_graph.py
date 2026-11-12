"""Automatic consistency checks on the graph + show a pasal's amendment chain.

usage: python eval/check_graph.py [--pasal 27] [--tanggal 2020-06-01]

Checks (validasi silang):
  C1  every 'mengubah'/'menghapus' (pasal) targets a pasal that already existed when the act took effect
  C2  every 'menyisipkan' targets a pasal that did NOT exist before, and the neighbours
      named in "di antara Pasal X dan Pasal Y" exist
  C3  every 'merujuk' to the consolidated act resolves to a pasal that exists at the time of the
      referencing version
  C4  per pasal: versions contiguous (berlaku_sampai of v_i == berlaku_sejak of v_i+1), exactly one
      version (or none) valid at the reference date
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = json.loads((ROOT / "data/output/graph/graph.json").read_text(encoding="utf-8"))
CONS = "uu-2008-11"


def existed(pid: str, on: str) -> bool:
    return any(v["berlaku_sejak"] < on or (v["ditetapkan_oleh"] == CONS and v["berlaku_sejak"] <= on) for v in G["versi"].get(pid, []))


def versi_pada(pid: str, tgl: str):
    return next((v for v in G["versi"].get(pid, []) if v["berlaku_sejak"] <= tgl and (v["berlaku_sampai"] is None or v["berlaku_sampai"] > tgl)), None)


def checks() -> list[str]:
    errs = []
    per = G["peraturan"]
    for e in G["edges"]:
        if "#pasal-" not in e["target"] or not e["target"].startswith(CONS):
            continue
        t_act = per.get(e.get("peraturan"), {}).get("tanggal_berlaku")
        if e["relasi"] in ("mengubah", "menghapus") and not existed(e["target"], t_act):
            errs.append(f"C1 {e['relasi']} target belum ada: {e['target']} (butir {e.get('butir')})")
        if e["relasi"] == "menyisipkan":
            if existed(e["target"], t_act):
                errs.append(f"C2 sisipan sudah ada sebelumnya: {e['target']}")
            for nb in (e.get("sisip_antara") or "").split(","):
                if nb and not existed(f"{CONS}#pasal-{nb}", t_act):
                    errs.append(f"C2 tetangga sisipan tidak ada: Pasal {nb} untuk {e['target']}")
        if e["relasi"] == "merujuk":
            src = next((v for vs in G["versi"].values() for v in vs if v["versi_id"] == e["source"]), None)
            if src and versi_pada(e["target"], src["berlaku_sejak"]) is None:
                errs.append(f"C3 rujukan tak ter-resolve: {e['source']} -> {e['target']} «{e['kutipan'][:90]}»")
    for pid, vs in G["versi"].items():
        for a, b in zip(vs, vs[1:]):
            if a["berlaku_sampai"] != b["berlaku_sejak"] and not a.get("sebab_berakhir"):
                errs.append(f"C4 versi tidak bersambung: {a['versi_id']} sampai {a['berlaku_sampai']} vs {b['versi_id']} sejak {b['berlaku_sejak']}")
        n_valid = sum(1 for v in vs if v["status"] in ("berlaku", "berlaku_sebagian", "dihapus"))
        if n_valid > 1:
            errs.append(f"C4 lebih dari satu versi berlaku: {pid}")
    return errs


def show_chain(nomor: str, tgl: str | None):
    pid = f"{CONS}#pasal-{nomor}"
    p = G["pasal"][pid]
    print(f"\n=== {pid}  status={p['status']}  versi_berlaku={p['versi_berlaku']}  induk={p['induk']}")
    for v in G["versi"][pid]:
        print(f"\n-- {v['versi_id']}  [{v['perubahan']}]  {v['berlaku_sejak']} → {v['berlaku_sampai'] or 'sekarang'}  status={v['status']}"
              + (f"  ayat_tidak_berlaku={v['ayat_tidak_berlaku']}" if v["ayat_tidak_berlaku"] else "")
              + (f"  ({v['sebab_berakhir']})" if v.get("sebab_berakhir") else ""))
        print("   " + (v["teks"][:600] + ("…" if len(v["teks"]) > 600 else "")))
    rel = [e for e in G["edges"] if e["target"] == pid and e["relasi"] not in ("versi_dari", "memuat")]
    print("\nrelasi masuk:")
    for e in rel:
        print(f"  {e['source']} -{e['relasi']}-> ({e.get('aturan')}, butir {e.get('butir', '-')}, ayat {e.get('ayat_target') or e.get('ayat_diubah') or '-'}) «{e['kutipan'][:110]}»")
    if tgl:
        v = versi_pada(pid, tgl)
        print(f"\nVersi yang berlaku pada {tgl}: {v['versi_id'] if v else '—'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasal", default="27")
    ap.add_argument("--tanggal", default=None)
    a = ap.parse_args()
    errs = checks()
    print(f"Validasi silang: {len(errs)} masalah")
    for e in errs:
        print("  ", e)
    show_chain(a.pasal, a.tanggal)
