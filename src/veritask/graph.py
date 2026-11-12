"""Assemble regulations, pasal, pasal versions and relations into one graph.

Versioning model (per pasal of the consolidated act UU 11/2008):
  Pasal (abstract)   uu-2008-11#pasal-27                    stable id, never changes
  PasalVersi         uu-2008-11#pasal-27@uu-2016-19          one per act that (re)states it
     berlaku_sejak   = tanggal_berlaku of the act that set this version
     berlaku_sampai  = berlaku_sejak of the next version, or an end date coming from a
                       'membatasi_keberlakuan' relation (Pasal II UU 1/2024 -> KUHP), else null
     ayat_berlaku_sampai = same, for single ayat
  Status is DERIVED from these relations as of a reference date, never typed in:
     pasal: berlaku | diubah | berlaku_sebagian | tidak_berlaku | dihapus
"""
from __future__ import annotations

import copy
import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .dates import berlaku_rule, parse_penutup
from .parse import iter_pasal
from .relations import (CONSOLIDATED, amendment_relations, dasar_hukum_relations, edge,
                        pasal_id, pasal_internal_relations)


def _induk(anc: list[dict]) -> str | None:
    """'BAB VII Perbuatan Yang Dilarang > Bagian Kesatu Umum' (metadata.judul_case fixes the casing)."""
    parts = []
    for a in anc:
        if a["type"] not in ("bab", "bagian", "paragraf"):
            continue
        judul = a.get("judul", "")
        if a["type"] == "bab":
            parts.append(f"BAB {a['nomor']}" + (f" {judul.title()}" if judul else ""))
        else:
            parts.append(f"{a['type'].capitalize()} {a['nomor']}" + (f" {judul}" if judul else ""))
    return " > ".join(parts) or None


def _root_num(n: str) -> str:
    return re.match(r"\d+", n).group(0)


_OCR_SUFFIX = {"8": "B", "4": "A", "6": "B", "0": "D"}


def _fix_ocr_target(e: dict, versions: dict) -> None:
    """'Pasal 278' (OCR of 27B) inside a reference: only when the literal target does not exist
    in the consolidated act AND the suffix-corrected one does. Original kept in target_ocr."""
    if e["relasi"] != "merujuk" or not e["target"].startswith(CONSOLIDATED + "#"):
        return
    if e["target"] in versions:
        _fix_ocr_ayat(e, versions)
        return
    n = e["target"].split("#pasal-")[1]
    if n.isdigit() and len(n) >= 2 and n[-1] in _OCR_SUFFIX:
        cand = pasal_id(CONSOLIDATED, n[:-1] + _OCR_SUFFIX[n[-1]])
        if cand in versions:
            e["target_ocr"], e["target"] = e["target"], cand
            e["aturan"] += "+ocr-fix"
            _fix_ocr_ayat(e, versions)


def _ayat_of(v: dict) -> set[str]:
    return {c["nomor"] for c in (v.get("struktur") or {}).get("children", []) if c["type"] == "ayat"}


def _fix_ocr_ayat(e: dict, versions: dict) -> None:
    """Referenced ayat must exist in *some* version of the target pasal. 'ayat (11)' read from
    '(1l' becomes '(1)' when (11) never existed but (1) did; unresolvable ayat are flagged."""
    if not e.get("ayat_target"):
        return
    known = set().union(*(_ayat_of(v) for v in versions[e["target"]]))
    fixed, bad = [], []
    for a in e["ayat_target"].split(","):
        if a in known:
            fixed.append(a)
        elif len(a) == 2 and a[1] == "1" and a[0] in known:
            fixed.append(a[0])
            e["ayat_target_ocr"] = e["ayat_target"]
            e["aturan"] += "+ocr-ayat"
        else:
            fixed.append(a)
            bad.append(a)
    e["ayat_target"] = ",".join(fixed)
    if bad:
        e["ayat_tidak_ditemukan"] = ",".join(bad)


def peraturan_record(doc: dict) -> dict:
    pen = parse_penutup(doc["penutup"]["teks"])
    m = re.match(r"uu-(\d{4})-(\d+)", doc["id"])
    rec = {"id": doc["id"], "jenis": "UU", "tahun": int(m.group(1)), "nomor": int(m.group(2)), **pen}
    # when does it take effect: Pasal II (amendments) / last pasal (UU induk)
    closing = ""
    for r in doc["batang_tubuh"]:
        if r["type"] == "pasal_romawi" and r["nomor"] == "II":
            closing = r["teks"]
    if not closing:
        last = list(iter_pasal(doc["batang_tubuh"]))[-1][0]
        closing = last["teks_lengkap"]
    rule = berlaku_rule(closing)
    rec["tanggal_berlaku"] = rec.get("tanggal_diundangkan") if rule == "diundangkan" else None
    rec["dasar_tanggal_berlaku"] = "mulai berlaku pada tanggal diundangkan" if rule else None
    return rec


def build(docs: dict[str, dict], ext: dict, as_of: str | None = None) -> dict:
    as_of = as_of or date.today().isoformat()
    perat = {pid: peraturan_record(d) for pid, d in docs.items()}
    for pid, e in ext["peraturan"].items():
        perat.setdefault(pid, {"id": pid, **e, "eksternal": True, "sumber_nilai": "manual_eksternal"})
    edges: list[dict] = []

    # ---------------- versions: original act
    base = docs[CONSOLIDATED]
    t0 = perat[CONSOLIDATED]["tanggal_berlaku"]
    versions: dict[str, list[dict]] = {}
    induk_by_root: dict[str, str | None] = {}
    for p, anc in iter_pasal(base["batang_tubuh"]):
        pid = pasal_id(CONSOLIDATED, p["nomor"])
        induk_by_root[p["nomor"]] = _induk(anc)
        versions[pid] = [{
            "versi_id": f"{pid}@{CONSOLIDATED}", "pasal_id": pid, "nomor": p["nomor"], "ditetapkan_oleh": CONSOLIDATED,
            "butir": None, "perubahan": "asli", "berlaku_sejak": t0, "berlaku_sampai": None,
            "teks": p["teks_lengkap"], "struktur": p, "penjelasan": p.get("penjelasan"),
            "penjelasan_dari": CONSOLIDATED if p.get("penjelasan") else None, "induk": _induk(anc),
            "halaman": p["halaman"], "ayat_berlaku_sampai": {},
        }]

    # ---------------- versions: amending acts in date order
    amenders = sorted((d for d in docs.values() if d["jenis_struktur"] == "perubahan"), key=lambda d: perat[d["id"]]["tanggal_berlaku"])
    for d in amenders:
        per, t = d["id"], perat[d["id"]]["tanggal_berlaku"]
        pen_entries = d["penjelasan"]["pasal_demi_pasal"] if d.get("penjelasan") else []
        roman_i = next(r for r in d["batang_tubuh"] if r["nomor"] == "I")
        for b in roman_i["children"]:
            content = {c["nomor"]: c for c in b["children"] if c["type"] == "pasal"}
            touched = list(dict.fromkeys(list(content) + b.get("pasal_target", []) + b.get("pasal_baru", [])))
            for n in touched:
                pid = pasal_id(CONSOLIDATED, n)
                prev = versions.get(pid, [None])[-1]
                if n in content:
                    c = content[n]
                    pen = c.get("penjelasan")
                    v = {
                        "versi_id": f"{pid}@{per}", "pasal_id": pid, "nomor": n, "ditetapkan_oleh": per, "butir": b["nomor"],
                        "perubahan": "sisipan" if prev is None else "isi", "berlaku_sejak": t, "berlaku_sampai": None,
                        "teks": c["teks_lengkap"], "struktur": c,
                        "penjelasan": pen or (prev or {}).get("penjelasan"),
                        "penjelasan_dari": per if pen else (prev or {}).get("penjelasan_dari"),
                        "induk": (prev or {}).get("induk") or induk_by_root.get(_root_num(n)),
                        "halaman": c["halaman"], "ayat_berlaku_sampai": {},
                    }
                elif "mengubah_penjelasan" in b.get("aksi", []) and prev is not None:
                    e = next((e for e in pen_entries if e.get("butir") == b["nomor"] and e["nomor"] == n), None)
                    v = copy.deepcopy(prev)
                    v.update({"versi_id": f"{pid}@{per}", "ditetapkan_oleh": per, "butir": b["nomor"], "perubahan": "penjelasan",
                              "berlaku_sejak": t, "berlaku_sampai": None, "ayat_berlaku_sampai": {},
                              "penjelasan": {"teks": e["teks_lengkap"], "children": e["children"]} if e else prev.get("penjelasan"),
                              "penjelasan_dari": per if e else prev.get("penjelasan_dari")})
                elif "menghapus" in b.get("aksi", []) and prev is not None:
                    v = {**copy.deepcopy(prev), "versi_id": f"{pid}@{per}", "ditetapkan_oleh": per, "butir": b["nomor"],
                         "perubahan": "dihapus", "teks": "", "struktur": None, "berlaku_sejak": t, "berlaku_sampai": None}
                else:
                    continue
                if prev is not None:
                    prev["berlaku_sampai"] = t
                versions.setdefault(pid, []).append(v)

    # ---------------- relations from text
    for d in amenders:
        edges += amendment_relations(d)
    for d in docs.values():
        edges += dasar_hukum_relations(d)

    # conditional end of validity (Pasal II UU 1/2024): close version / ayat
    for e in [e for e in edges if e["relasi"] == "membatasi_keberlakuan"]:
        cond = e.get("sampai_berlakunya")
        end = perat.get(cond, {}).get("tanggal_berlaku")
        start = perat[e["peraturan"]]["tanggal_berlaku"]
        e["tanggal_akhir"] = end
        e["sumber_tanggal_akhir"] = "manual_eksternal" if perat.get(cond, {}).get("eksternal") else "korpus"
        vs = versions.get(e["target"], [])
        v = next((v for v in vs if v["berlaku_sejak"] <= start and (v["berlaku_sampai"] is None or v["berlaku_sampai"] > start)), None)
        if v is None or end is None:
            continue
        if e.get("ayat_target"):
            for a in e["ayat_target"].split(","):
                v["ayat_berlaku_sampai"][f"({a})"] = end
        elif v["berlaku_sampai"] is None or v["berlaku_sampai"] > end:
            v["berlaku_sampai"] = end
            v["sebab_berakhir"] = f"{e['peraturan']} {e.get('lokasi')}: berlaku sampai diberlakukannya {cond}"

    # internal relations per version (merujuk / mendelegasikan) + version edges
    for pid, vs in versions.items():
        for i, v in enumerate(vs):
            if v["struktur"]:
                for e in pasal_internal_relations(v["versi_id"], v["ditetapkan_oleh"], v["struktur"], v["halaman"]):
                    _fix_ocr_target(e, versions)
                    edges.append(e)
            edges.append(edge(v["ditetapkan_oleh"], v["versi_id"], "menetapkan_versi", "R-versi", "", peraturan=v["ditetapkan_oleh"], butir=v["butir"]))
            edges.append(edge(v["versi_id"], pid, "versi_dari", "R-versi", ""))
            if i > 0:
                edges.append(edge(v["versi_id"], vs[i - 1]["versi_id"], "menggantikan", "R-versi", "", peraturan=v["ditetapkan_oleh"], butir=v["butir"]))
        edges.append(edge(CONSOLIDATED, pid, "memuat", "R-memuat", ""))

    # ---------------- derived status
    pasal_nodes = {}
    for pid, vs in versions.items():
        cur = next((v for v in vs if v["berlaku_sejak"] <= as_of and (v["berlaku_sampai"] is None or v["berlaku_sampai"] > as_of)), None)
        for v in vs:
            ended = {a: d for a, d in v["ayat_berlaku_sampai"].items() if d <= as_of}
            if v is cur:
                v["status"] = "dihapus" if v["perubahan"] == "dihapus" else ("berlaku_sebagian" if ended else "berlaku")
            else:
                v["status"] = "belum_berlaku" if v["berlaku_sejak"] > as_of else "tidak_berlaku"
            v["ayat_tidak_berlaku"] = sorted(ended)
        last = vs[-1]
        if cur is None:
            status = "tidak_berlaku" if last["perubahan"] != "dihapus" else "dihapus"
        elif cur["status"] == "dihapus":
            status = "dihapus"
        elif cur["status"] == "berlaku_sebagian":
            status = "berlaku_sebagian"
        elif len(vs) > 1:
            status = "diubah"
        else:
            status = "berlaku"
        pasal_nodes[pid] = {"id": pid, "nomor": vs[0]["nomor"], "peraturan_id": CONSOLIDATED, "status": status,
                            "versi_berlaku": cur["versi_id"] if cur else None, "jumlah_versi": len(vs),
                            "diubah_terakhir_oleh": next((v["ditetapkan_oleh"] for v in reversed(vs) if v["ditetapkan_oleh"] != CONSOLIDATED), None),
                            "induk": last["induk"]}

    # regulation status, derived from incoming relations
    for pid, rec in perat.items():
        inc = [e for e in edges if e["target"] == pid or e["target"].startswith(pid + "#")]
        rels = {e["relasi"] for e in inc}
        if any(e["relasi"] == "mencabut" and e["target"] == pid for e in inc):
            rec["status"] = "dicabut"
        elif pid == CONSOLIDATED and any(p["status"] in ("tidak_berlaku", "dihapus") for p in pasal_nodes.values()):
            rec["status"] = "dicabut_sebagian" if "mengubah" not in rels else "diubah"
            rec["catatan_status"] = "diubah; sebagian ketentuan tidak berlaku lagi per " + as_of
        elif rels & {"mengubah", "menyisipkan", "menghapus"}:
            rec["status"] = "diubah"
        else:
            rec["status"] = "berlaku" if not rec.get("eksternal") else None
        rec["status_per_tanggal"] = as_of
    return {"as_of": as_of, "peraturan": perat, "pasal": pasal_nodes, "versi": versions, "edges": edges}


# ------------------------------------------------------------------ export
NODE_COLS = ["id:ID", ":LABEL", "nama", "jenis", "nomor", "tahun", "status", "berlaku_sejak", "berlaku_sampai",
             "ditetapkan_oleh", "perubahan", "induk", "teks"]
EDGE_COLS = [":START_ID", ":END_ID", ":TYPE", "aturan", "peraturan", "butir", "lokasi", "pasal", "ayat_sumber",
             "ayat_target", "bagian", "ayat_diubah", "sisip_antara", "sampai_berlakunya", "tanggal_akhir", "halaman", "kutipan"]


def export(g: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    nodes: dict[str, dict] = {}
    for p in g["peraturan"].values():
        nodes[p["id"]] = {"id:ID": p["id"], ":LABEL": "Peraturan" + (";Eksternal" if p.get("eksternal") else ""), "nama": p.get("judul", p["id"]),
                          "jenis": p.get("jenis"), "nomor": p.get("nomor"), "tahun": p.get("tahun"), "status": p.get("status"),
                          "berlaku_sejak": p.get("tanggal_berlaku")}
    for p in g["pasal"].values():
        nodes[p["id"]] = {"id:ID": p["id"], ":LABEL": "Pasal", "nama": f"Pasal {p['nomor']}", "nomor": p["nomor"], "status": p["status"], "induk": p["induk"]}
    for vs in g["versi"].values():
        for v in vs:
            nodes[v["versi_id"]] = {"id:ID": v["versi_id"], ":LABEL": "PasalVersi", "nama": f"Pasal {v['nomor']} ({v['ditetapkan_oleh']})",
                                    "nomor": v["nomor"], "status": v["status"], "berlaku_sejak": v["berlaku_sejak"],
                                    "berlaku_sampai": v["berlaku_sampai"], "ditetapkan_oleh": v["ditetapkan_oleh"],
                                    "perubahan": v["perubahan"], "induk": v["induk"], "teks": v["teks"]}
    for e in g["edges"]:  # stub nodes for targets outside the corpus
        for k in ("source", "target"):
            nid = e[k]
            if nid in nodes:
                continue
            if nid.startswith("delegasi:"):
                nodes[nid] = {"id:ID": nid, ":LABEL": "PeraturanPelaksana", "nama": f"{nid.split(':')[1]} pelaksana (belum diidentifikasi)"}
            elif "#pasal-" in nid:
                nodes[nid] = {"id:ID": nid, ":LABEL": "Pasal;Eksternal", "nama": nid}
            else:
                nodes[nid] = {"id:ID": nid, ":LABEL": "Peraturan;Eksternal", "nama": nid}
    with open(out_dir / "nodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, NODE_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(nodes.values())
    with open(out_dir / "edges.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, EDGE_COLS, extrasaction="ignore")
        w.writeheader()
        for e in g["edges"]:
            w.writerow({":START_ID": e["source"], ":END_ID": e["target"], ":TYPE": e["relasi"].upper(), **e})
    _cypher(nodes, g["edges"], out_dir / "load_neo4j.cypher")
    # graph.json: same content, with the bulky "struktur" tree moved to the end of each version
    slim = {k: v for k, v in g.items() if k != "versi"}
    slim["versi"] = {pid: [{k: v for k, v in x.items() if k != "struktur"} | {"struktur": x["struktur"]} for x in vs]
                     for pid, vs in g["versi"].items()}
    (out_dir / "graph.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")


def _q(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def _cypher(nodes: dict, edges: list[dict], path: Path) -> None:
    L = ["// Generated by veritask.graph — run in an empty Neo4j database",
         "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE;"]
    for n in nodes.values():
        labels = ":".join(["Node"] + n[":LABEL"].split(";"))
        props = {("id" if k == "id:ID" else k): v for k, v in n.items() if k != ":LABEL" and v not in (None, "")}
        L.append(f"MERGE (n:{labels} {{id: {_q(props['id'])}}}) SET n += {{{', '.join(f'{k}: {_q(v)}' for k, v in props.items())}}};")
    for e in edges:
        props = {k: v for k, v in e.items() if k not in ("source", "target", "relasi") and v not in (None, "")}
        L.append(f"MATCH (a:Node {{id: {_q(e['source'])}}}), (b:Node {{id: {_q(e['target'])}}}) "
                 f"CREATE (a)-[:{e['relasi'].upper()} {{{', '.join(f'{k}: {_q(v)}' for k, v in props.items())}}}]->(b);")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
