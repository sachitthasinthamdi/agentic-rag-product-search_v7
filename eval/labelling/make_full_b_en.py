r"""สร้างไฟล์ป้าย ข ฝั่งอังกฤษกองเต็ม — กอง g1 ทั้ง 50 คำค้น ยกป้ายชุด 15 ข้อเดิมมา

ชุด 15 ข้อเดิม (labels_b3.csv) สุ่มมาจากกองนี้ จึงยกป้ายกับหมายเหตุมาได้ตรง ๆ
ที่เหลืออีก 35 ข้อต้องอ่านคำตอบแล้วติดป้ายใหม่ด้วยเกณฑ์เดียวกัน

รัน:  .venv\Scripts\python.exe eval\labelling\make_full_b_en.py
"""
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "eval" / "results" / "collection_20261013_1329.json"
LAB = ROOT / "eval" / "labels"
OUT = LAB / "labels_b3_full.csv"


def main() -> None:
    if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    raw = json.loads(RES.read_text(encoding="utf-8"))["raw"]["A3_r1"]
    g1 = [g for g in raw if "g1" in g or "in_domain" in g][0]
    old = {r["qid"]: r for r in csv.DictReader((LAB / "labels_b3.csv").open(encoding="utf-8-sig", newline=""))}

    rows = []
    for i, qid in enumerate(sorted(raw[g1]), 1):
        rec = raw[g1][qid]
        pk = rec.get("picked") or []
        if not pk:
            continue
        o = old.get(qid)
        rows.append({
            "ans_id": f"e{i:02d}",
            "qid": qid,
            "query": rec["q"],
            "n_products": len(pk),
            "label": o["label"] if o else "",
            "kind": o["kind"] if o else "",
            "note": (o["note"].rstrip() + "  [ยกมาจากชุด 15 ข้อเดิม]") if o else "",
        })

    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    done = sum(1 for r in rows if r["label"].strip())
    print(f"เขียน {OUT.name} · {len(rows)} แถว · ยกป้ายมาแล้ว {done} · เหลือติด {len(rows)-done}")


if __name__ == "__main__":
    main()
