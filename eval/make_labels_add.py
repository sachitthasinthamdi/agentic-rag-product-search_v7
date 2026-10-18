"""สร้างไฟล์ติดป้าย **เฉพาะส่วนที่ยังไม่มีป้าย** จากผลรันรอบใหม่

ใช้เมื่อรันรอบใหม่แล้วระบบหยิบสินค้าชิ้นที่กองป้ายเดิมไม่ครอบคลุม
เช่นรอบภาษาไทยหยิบของคนละชุดราวครึ่งหนึ่ง

**ป้ายเดิมไม่ถูกแตะ** — ไฟล์ใหม่มีแต่คู่ที่ยังไม่เคยติด แล้วรวมกันตอนคิดคะแนน
รหัส `pair_id` นับต่อจากไฟล์เดิม ไม่ชนกัน

⚠ ปิดตาเหมือนเดิม: ไม่มีคอลัมน์ แขน · รอบ · อันดับ · คะแนน · ชั้นความยาก
  และสลับลำดับสินค้าในแต่ละคำค้นด้วยเมล็ดสุ่มคงที่

⚠ **แสดงคำค้นภาษาอังกฤษเป็นหลัก** เพื่อให้เกณฑ์ตรงกับป้าย 152 คู่เดิมที่ติดจากคำอังกฤษ
  ความตรงไม่ขึ้นกับภาษาที่พิมพ์ · ใส่คำไทยไว้ให้ดูประกอบ

รัน:  python eval\\make_labels_add.py eval\\results\\collection_th_xxx.json
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
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.collection import (GROUP1_IN_DOMAIN, GROUP3_OUT_OF_DOMAIN,  # noqa: E402
                             GROUP4_BUDGET)
from eval.collection_th import thai_query                        # noqa: E402

LAB_DIR = ROOT / "eval" / "labels"
# ⚠ ต้องอ่าน **ทุกไฟล์ป้าย** ไม่ใช่แค่ไฟล์แรก
# เคยอ่านแค่ labels_a.csv ทำให้ของที่ติดไว้แล้วใน labels_a2.csv ถูกนับเป็นของใหม่
BASES = sorted(LAB_DIR.glob("labels_a*.csv"))
SEED = 20261004
DETAIL_CHARS = 300
# ⚠ ต้องครบ **ทั้ง 3 กลุ่ม** — เดิมมีแค่ g1 ทำให้คู่ของ g3 กับ g4 หลุดหมด
# (รอบ 2026-10-12 g4 เพิ่งเข้าชุดทดสอบ จึงไม่มีป้ายเลยแม้คู่เดียว)
GROUPS = {"g1": GROUP1_IN_DOMAIN, "g3": GROUP3_OUT_OF_DOMAIN,
          "g4": GROUP4_BUDGET}
QEN = {x["id"]: x["q"] for items in GROUPS.values() for x in items}
QGROUP = {x["id"]: g for g, items in GROUPS.items() for x in items}

FIELDS = ["pair_id", "qid", "query", "query_th", "product_title", "category",
          "price", "store", "details", "label", "note"]


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="สร้างไฟล์ติดป้ายเฉพาะส่วนที่ขาด")
    ap.add_argument("results", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, default=LAB_DIR / "labels_a2.csv")
    args = ap.parse_args()

    base = []
    for b in BASES:
        if b.name.endswith(("_check.csv", "_pilot.csv")) or b == args.out:
            continue            # กองตรวจของคนที่สองไม่ใช่ป้าย ไม่นับ
        with b.open(encoding="utf-8-sig", newline="") as fh:
            base += list(csv.DictReader(fh))
    have = {(r["qid"], r["product_title"]) for r in base}
    start = max(int(r["pair_id"][1:]) for r in base)
    print(f"ป้ายเดิม {len(base)} คู่ จาก {len(BASES)} ไฟล์ · "
          f"รหัสใหม่เริ่มที่ a{start + 1:03d}")

    # เก็บคู่ที่ยังไม่มีป้าย จากทุกไฟล์ผลที่ส่งมา
    need: dict[tuple[str, str], dict] = {}
    for f in args.results:
        raw = json.loads(f.read_text(encoding="utf-8"))["raw"]
        for arm_round in raw.values():
            for g in GROUPS:
                for qid, rec in arm_round.get(g, {}).items():
                    for p in rec["picked"]:
                        key = (qid, p["title"])
                        if key not in have:
                            need.setdefault(key, {**p, "qid": qid})
    print(f"คู่ที่ยังไม่มีป้าย {len(need)} คู่ ใน {len({q for q, _ in need})} คำค้น")

    # เติมคำบรรยายสินค้าจากคลัง
    n_det = 0
    try:
        from retrieval import Retriever
        with Retriever() as rt:
            for p in need.values():
                hit = rt.get(p["id"])
                if hit is not None and hit.document:
                    p["details"] = " ".join(hit.document[:DETAIL_CHARS].split())
                    n_det += 1
    except Exception as exc:                                     # noqa: BLE001
        print(f"  ⚠ ต่อคลังไม่ได้ ({type(exc).__name__}) — ไฟล์จะไม่มีคำบรรยาย")
    print(f"เติมคำบรรยายได้ {n_det}/{len(need)}")

    by_q: dict[str, list[dict]] = {}
    for (qid, _), p in need.items():
        by_q.setdefault(qid, []).append(p)
    rng = random.Random(SEED)
    rows = []
    for qid in sorted(by_q):
        items = by_q[qid]
        rng.shuffle(items)                 # ⚠ กันการเดาอันดับที่ระบบให้ไว้
        for p in items:
            rows.append({
                "pair_id": "", "qid": qid, "query": QEN[qid],
                "query_th": thai_query(QGROUP[qid], qid, QEN[qid]),
                "product_title": p["title"], "category": p.get("category", ""),
                "price": "" if p.get("price") is None else p["price"],
                "store": p.get("store", ""), "details": p.get("details", ""),
                "label": "", "note": ""})
    for i, r in enumerate(rows, start + 1):
        r["pair_id"] = f"a{i:03d}"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nเขียน {args.out.name} · {len(rows)} คู่ "
          f"({rows[0]['pair_id']} - {rows[-1]['pair_id']})")


if __name__ == "__main__":
    main()
