"""สร้างไฟล์ป้าย ข รอบใหม่ — ความซื่อตรงของคำตอบ

⚠ **ใช้วิธีเดียวกับ `make_labels.py` เป๊ะ** เพื่อให้ตัวเลขใหม่เทียบกับรอบเก่าได้
    เมล็ดสุ่ม `SEED + 2` เดิม · กลุ่ม g1 เท่านั้น · 15 คำตอบ · กรองโหมดอ่อนออก
→ ได้**คำค้นชุดเดียวกับรอบเก่า** ต่างกันแค่คำตอบ เพราะ Reranker หยิบของคนละชุด

**แขนที่ใช้** A3 เหมือนรอบเก่า (ตอนนั้นมีแขนเดียว) · Generator เป็นชิ้นส่วนร่วม
ของทุกแขน และในกลุ่ม g1 ทุกแขนหยิบของชุดเดียวกัน จึงเลือกแขนไหนก็ได้ผลเท่ากัน

⚠ **ไม่เขียนทับ `labels_b.csv`** ที่ผู้ใช้กรอกไว้ครบ 15 ข้อ (EN 76.7% · TH 36.7%)
    ไฟล์ใหม่ชื่อ `labels_b2*` เพื่อให้เทียบสองรอบได้

รัน:  python eval\\make_labels_b2.py eval\\results\\collection_20261012_1623.json
      python eval\\make_labels_b2.py eval\\results\\collection_th_20261012_1820.json --th
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "eval" / "labels"
SEED = 20261003          # เมล็ดเดิมของ make_labels.py
ANSWERS_N = 15
ARM = "A3_r1"

FIELDS = ["ans_id", "qid", "query", "n_products", "label", "kind", "note"]


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="สร้างไฟล์ป้าย ข รอบใหม่")
    ap.add_argument("results", type=Path)
    ap.add_argument("--th", action="store_true", help="รอบภาษาไทย")
    ap.add_argument("--gen", default="2", help="รุ่นของไฟล์ป้าย เช่น 2 หรือ 3")
    ap.add_argument("--arm", default=ARM)
    args = ap.parse_args()

    raw = json.loads(args.results.read_text(encoding="utf-8"))["raw"]
    if args.arm not in raw:
        raise SystemExit(f"❌ ไม่มีแขน {args.arm} · มี {list(raw)}")
    arm = raw[args.arm]

    # ⚠ กรองโหมดอ่อนออก — โค้ดเขียนเองทั้งก้อน จึงซื่อตรง 100% โดยโครงสร้าง
    # ถ้านับรวมจะเป็นการให้คะแนนฟรี (docs/eval_plan.md ข้อ 4 ส่วน ข)
    pool = [(qid, r) for qid, r in arm.get("g1", {}).items()
            if r["picked"] and not r["weak"] and r["context"]]
    pool.sort()
    chosen = random.Random(SEED + 2).sample(pool, min(ANSWERS_N, len(pool)))
    chosen.sort()

    tag = "_th" if args.th else ""
    csv_path = OUT_DIR / f"labels_b{args.gen}{tag}.csv"
    md_path = OUT_DIR / f"labels_b{args.gen}{tag}_read.md"
    lang = "ไทย" if args.th else "อังกฤษ"

    rows, md = [], [
        f"# ป้าย ข รอบใหม่ — ความซื่อตรงของคำตอบ ({lang})", "",
        f"แขน `{args.arm}` · กลุ่ม g1 · {len(chosen)} คำตอบ · "
        f"คำค้นชุดเดียวกับรอบเก่า (เมล็ดสุ่มเดิม)", "",
        f"อ่านไฟล์นี้ แล้วกรอกคะแนนลง `labels_b{args.gen}{tag}.csv` โดยใช้ `ans_id` จับคู่กัน", "",
        "คำถามที่ต้องตอบคือ **ให้ข้อมูลมาเท่านี้ ระบบเขียนเกินข้อมูลไหม**",
        "ไม่ใช่ว่าระบบหาของเก่งไหม — เรื่องนั้นวัดไปแล้วในป้าย ก", "",
        "เกณฑ์: **2** ทุกข้อความมีข้อมูลรองรับ · **1** ขยายความเกินนิดหน่อยแต่ไม่ผิด"
        " · **0** มีข้อความที่ข้อมูลไม่รองรับหรือขัดกับข้อมูล", "",
        "ถ้าให้ 0 หรือ 1 ระบุชนิดด้วย: `intrinsic` บิดเบือนข้อมูลที่ให้ ·"
        " `extrinsic` เติมสิ่งที่ไม่มีในข้อมูล", "",
        "⚠ **การทวนคำของผู้ใช้ไม่ใช่การแต่งข้อมูล** · "
        "**การบอกตรง ๆ ว่าของไม่ตรงถือว่าดี** ให้ 2", "", "---", ""]

    for i, (qid, r) in enumerate(chosen, 1):
        aid = f"b{i:02d}"
        rows.append({"ans_id": aid, "qid": qid, "query": r["q"],
                     "n_products": len(r["picked"]), "label": "",
                     "kind": "", "note": ""})
        md += [f"## {aid}", "", f'**ผู้ใช้ถาม:** {r["q"]}', "",
               "**ข้อเท็จจริงที่ระบบมีอยู่ในมือ**", "", "```",
               r["context"], "```", "",
               "**คำตอบที่ระบบเขียน**", "", "```", r["reply"], "```", "",
               f"ให้คะแนน `{aid}` = ____   ชนิด = ____", "", "---", ""]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"กองที่เลือกได้ {len(pool)} คำตอบ · สุ่มมา {len(rows)}")
    print(f"เขียน {csv_path.name} · {md_path.name}")
    print(f"คำค้น: {', '.join(qid for qid, _ in chosen)}")


if __name__ == "__main__":
    main()
