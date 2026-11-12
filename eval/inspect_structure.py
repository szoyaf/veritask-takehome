"""Print a compact outline of a structured JSON for eyeballing / sanity checks.

usage: python eval/inspect_structure.py data/output/structured/uu-2024-1.json
"""
import json
import sys


def outline(n, depth=0, out=None):
    out = out if out is not None else []
    t = n["type"]
    if t in ("bab", "bagian", "paragraf"):
        out.append("  " * depth + f"{t.upper()} {n['nomor']} — {n.get('judul', '')[:60]}")
    elif t == "pasal_romawi":
        out.append("  " * depth + f"PASAL {n['nomor']} (romawi) {n.get('teks', '')[:70]!r}")
    elif t == "butir":
        out.append("  " * depth + f"butir {n['nomor']}: aksi={n.get('aksi')} target={n.get('pasal_target')} baru={n.get('pasal_baru')}")
    elif t == "pasal":
        ayat = [c["nomor"] for c in n["children"] if c["type"] == "ayat"]
        sub = [c["type"][0] + c["nomor"] for c in n["children"] if c["type"] != "ayat"]
        pen = "P" if "penjelasan" in n else "-"
        ocr = f" (ocr:{n['nomor_ocr']})" if n.get("nomor_ocr") else ""
        out.append("  " * depth + f"Pasal {n['nomor']}{ocr} [{pen}] ayat={ayat} {sub[:8]} p{n['halaman']} len={len(n['teks_lengkap'])}")
        return out
    for c in n.get("children", []):
        outline(c, depth + 1, out)
    return out


def main(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    print(doc["id"], doc["jenis_struktur"], "|", doc["judul_dokumen"][:100])
    k = doc["konsiderans"]
    print("menimbang:", [c["nomor"] for c in k["menimbang"]["children"]],
          " mengingat:", [c["nomor"] for c in k["mengingat"]["children"]] or "(1 item)")
    for n in doc["batang_tubuh"]:
        print("\n".join(outline(n)))
    pen = doc["penjelasan"]
    print("penjelasan umum chars:", len(pen["umum"]), "| entries:", len(pen["pasal_demi_pasal"]), "| TLN:", pen["tln_raw"])
    unl = [(e.get("butir"), e["nomor"]) for e in pen["pasal_demi_pasal"] if not e.get("menjelaskan") and not e.get("pasal_romawi")]
    print("penjelasan tidak tertaut:", unl)
    print("penutup:", doc["penutup"]["teks"][:300])


if __name__ == "__main__":
    main(sys.argv[1])
