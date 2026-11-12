"""Build and validate metadata records (Bagian 2) from structured docs + graph.

Outputs (data/output/metadata/):
  peraturan.json            one PeraturanMetadata per regulation in the corpus
  pasal.jsonl               one PasalMetadata per pasal VERSION (pasal_id repeats across versions)
  schema_peraturan.json, schema_pasal.json   JSON Schema with `asal` per field
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .schema import Bidang, PasalMetadata, PeraturanMetadata

# ------------------------------------------------------------------ casing
_SMALL = {"dan", "atau", "yang", "di", "ke", "dari", "untuk", "atas", "tentang", "dalam", "pada", "serta", "dengan", "oleh"}


def judul_case(s: str) -> str:
    words = re.sub(r"\s+", " ", s.strip()).split(" ")
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i > 0 and lw in _SMALL:
            out.append(lw)
        elif re.fullmatch(r"[IVXLC]+", w):
            out.append(w)
        else:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
    return " ".join(out)


# ------------------------------------------------------------------ bidang classifier ("model")
# Keyword rules, deliberately simple and inspectable. Marked asal=model in the schema.
BIDANG_RULES: dict[str, list[str]] = {
    "pidana": [r"\bdipidana\b", r"pidana penjara", r"\bdenda\b", r"tindak pidana", r"\bpemidanaan\b"],
    "acara pidana & penyidikan": [r"\bpenyidik", r"penyidikan", r"penggeledahan", r"penyitaan", r"penangkapan", r"\bpenahanan\b"],
    "konten dilarang": [r"kesusilaan", r"perjudian", r"kehormatan atau nama baik", r"pencemaran", r"pemerasan", r"pengancaman",
                        r"berita bohong", r"kebencian", r"ancaman kekerasan"],
    "tanda tangan & sertifikasi elektronik": [r"Tanda Tangan Elektronik", r"Sertifikat Elektronik", r"Penyelenggara Sertifikasi", r"segel elektronik"],
    "penyelenggaraan sistem elektronik": [r"Penyelenggara(?:an)? Sistem Elektronik", r"andal dan aman"],
    "transaksi & kontrak elektronik": [r"Transaksi Elektronik", r"Kontrak Elektronik", r"klausula baku", r"pelaku usaha"],
    "alat bukti elektronik": [r"alat bukti", r"Dokumen Elektronik dan/atau hasil cetaknya"],
    "perlindungan anak": [r"\banak\b"],
    "data pribadi & privasi": [r"data pribadi", r"privasi", r"intersepsi", r"penyadapan"],
    "nama domain & HKI": [r"Nama Domain", r"kekayaan intelektual"],
    "kewenangan pemerintah": [r"Pemerintah (?:berwenang|wajib|melindungi|mendorong)", r"pemutusan Akses", r"Pemerintah bertanggung jawab"],
    "sanksi administratif": [r"sanksi administratif", r"teguran tertulis"],
}


def classify(text: str, top: int = 3) -> list[Bidang]:
    hits = Counter()
    for label, pats in BIDANG_RULES.items():
        for p in pats:
            hits[label] += len(re.findall(p, text, flags=re.I if p.islower() else 0))
    total = sum(hits.values())
    if not total:
        return [Bidang(label="umum", skor=0.0)]
    return [Bidang(label=k, skor=round(v / total, 3)) for k, v in hits.most_common(top) if v]


# ------------------------------------------------------------------ helpers
def _lapisan_teks(pdf_path: Path) -> str:
    import pymupdf

    pymupdf.TOOLS.mupdf_display_errors(False)
    with pymupdf.open(pdf_path) as d:
        covs = []
        for p in list(d)[:5]:
            area = p.rect.get_area()
            covs.append(max((p.get_image_bbox(i).get_area() / area for i in p.get_images(full=True)), default=0))
    return "ocr_bawaan" if sum(c > 0.9 for c in covs) >= len(covs) / 2 else "digital"


def _units(n: dict | None, ayat_end: dict) -> list[dict]:
    if not n:
        return []
    out = []
    for c in n.get("children", []):
        u = {"jenis": c["type"], "nomor": c["nomor"], "teks": c["teks"], "anak": _units(c, {})}
        if c["type"] == "ayat" and ayat_end.get(f"({c['nomor']})"):
            u["berlaku_sampai"] = ayat_end[f"({c['nomor']})"]
        out.append(u)
    return out


def _split_induk(induk: str | None) -> dict:
    """'BAB VII Perbuatan Yang Dilarang > Bagian Kesatu ...' -> {"bab": "BAB VII Perbuatan yang Dilarang", ...}"""
    out = {"bab": None, "bagian": None, "paragraf": None}
    for part in (induk or "").split(" > "):
        words = part.strip().split(" ")
        key = words[0].lower()
        if key == "bab":  # keep the roman numeral as is, fix the casing of the title
            out[key] = " ".join(["BAB", words[1]] + ([judul_case(" ".join(words[2:]))] if len(words) > 2 else []))
        elif key in out:
            out[key] = words[0] + " " + judul_case(" ".join(words[1:]))
    return out


# ------------------------------------------------------------------ builders
def build_peraturan(docs: dict, g: dict, sources: dict, root: Path) -> list[PeraturanMetadata]:
    out = []
    for pid, doc in docs.items():
        rec = g["peraturan"][pid]
        src = sources[pid]
        head = re.sub(r"\s+", " ", doc["judul_dokumen"])
        m = re.search(r"TENTANG (.+)$", head)
        tentang_full = judul_case(m.group(1)) if m else ""
        core = re.split(r"\btentang\b", tentang_full)[-1].strip()
        persetujuan = re.findall(r"(DEWAN PERWAKILAN RAKYAT REPUBLIK INDONESIA|DEWAN PERWAKILAN DAERAH REPUBLIK INDONESIA|PRESIDEN REPUBLIK INDONESIA)",
                                 doc["diktum"].get("persetujuan_bersama") or "")
        n_pasal = sum(1 for vs in g["versi"].values() for v in vs if v["ditetapkan_oleh"] == pid and v["perubahan"] in ("isi", "sisipan", "asli"))
        out_edges = [e for e in g["edges"] if e["source"] == pid]
        in_edges = [e for e in g["edges"] if e["target"] == pid or e["target"].startswith(pid + "#")]
        all_text = " ".join(v["teks"] for vs in g["versi"].values() for v in vs if v["ditetapkan_oleh"] == pid)
        out.append(PeraturanMetadata(
            id=pid, jenis="UU", nomor=rec["nomor"], tahun=rec["tahun"],
            judul=f"Undang-Undang Nomor {rec['nomor']} Tahun {rec['tahun']} tentang {tentang_full}",
            tentang=core, judul_singkat=f"UU {rec['nomor']}/{rec['tahun']}",
            jenis_struktur=doc["jenis_struktur"],
            pembentuk=[judul_case(p) for p in dict.fromkeys(persetujuan)],
            pemrakarsa=None,
            penandatangan=rec.get("penandatangan"), jabatan_penandatangan=rec.get("jabatan_penandatangan"),
            pengundang=rec.get("pengundang"), jabatan_pengundang=judul_case(rec["jabatan_pengundang"]) if rec.get("jabatan_pengundang") else None,
            tanggal_ditetapkan=rec["tanggal_ditetapkan"], tanggal_diundangkan=rec["tanggal_diundangkan"],
            tanggal_berlaku=rec.get("tanggal_berlaku"), dasar_tanggal_berlaku=rec.get("dasar_tanggal_berlaku"),
            lembaran_negara=rec.get("lembaran_negara"),
            tambahan_lembaran_negara=(lambda t: f"TLN Nomor {t.group(1)}" if t else None)(
                re.search(r"NOMOR (\d+)", (doc.get("penjelasan") or {}).get("tln_raw") or "")),
            status=rec["status"], status_per_tanggal=rec["status_per_tanggal"],
            mengubah=sorted({e["target"] for e in out_edges if e["relasi"] == "mengubah" and "#" not in e["target"]}),
            diubah_oleh=sorted({e["source"] for e in in_edges if e["relasi"] in ("mengubah", "menyisipkan")}),
            dasar_hukum=sorted({e["target"] for e in out_edges if e["relasi"] == "dasar_hukum"}),
            jumlah_pasal=n_pasal,
            bidang=classify(all_text),
            sumber_url=src["sumber_url"], halaman_sumber=src.get("detail_url"), tanggal_unduh=src["tanggal_unduh"],
            hash_file=src["hash_file"], jumlah_halaman=doc["jumlah_halaman"], metode_ekstraksi=doc["metode_ekstraksi"],
            lapisan_teks=_lapisan_teks(root / src["file"]),
        ))
    return out


def build_pasal(g: dict) -> list[PasalMetadata]:
    refs_out, refs_in, deleg = defaultdict(set), defaultdict(set), defaultdict(set)
    for e in g["edges"]:
        if e["relasi"] == "merujuk":
            refs_out[e["source"]].add(e["target"])
            refs_in[e["target"]].add(e["source"])
        elif e["relasi"] == "mendelegasikan":
            deleg[e["source"]].add(e["target"].split(":")[1])
    out = []
    for pid, vs in g["versi"].items():
        pas = g["pasal"][pid]
        for i, v in enumerate(vs):
            ind = _split_induk(v.get("induk"))
            pen = v.get("penjelasan")
            out.append(PasalMetadata(
                pasal_id=pid, versi_id=v["versi_id"], peraturan_id=pas["peraturan_id"], nomor=v["nomor"],
                **ind, teks=v["teks"], ayat=_units(v.get("struktur"), v.get("ayat_berlaku_sampai", {})),
                penjelasan={"teks": pen["teks"], "sumber_peraturan": v.get("penjelasan_dari") or v["ditetapkan_oleh"]} if pen else None,
                ditetapkan_oleh=v["ditetapkan_oleh"], butir_perubahan=v.get("butir"), jenis_perubahan=v["perubahan"],
                berlaku_sejak=v["berlaku_sejak"], berlaku_sampai=v["berlaku_sampai"], sebab_berakhir=v.get("sebab_berakhir"),
                ayat_tidak_berlaku=v.get("ayat_tidak_berlaku", []), status=v["status"], status_per_tanggal=g["as_of"],
                diubah_terakhir_oleh=pas["diubah_terakhir_oleh"], versi_sebelumnya=vs[i - 1]["versi_id"] if i else None,
                merujuk=sorted(refs_out[v["versi_id"]]), dirujuk_oleh=sorted(refs_in[pid]),
                mendelegasikan=sorted(deleg[v["versi_id"]]), bidang=classify(v["teks"]), halaman=v.get("halaman"),
            ))
    return out


def export(peraturan: list[PeraturanMetadata], pasal: list[PasalMetadata], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "peraturan.json").write_text(
        json.dumps([p.model_dump(mode="json") for p in peraturan], ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out_dir / "pasal.jsonl", "w", encoding="utf-8") as f:
        for p in pasal:
            f.write(json.dumps(p.model_dump(mode="json"), ensure_ascii=False) + "\n")
    (out_dir / "schema_peraturan.json").write_text(json.dumps(PeraturanMetadata.model_json_schema(), ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "schema_pasal.json").write_text(json.dumps(PasalMetadata.model_json_schema(), ensure_ascii=False, indent=1), encoding="utf-8")
