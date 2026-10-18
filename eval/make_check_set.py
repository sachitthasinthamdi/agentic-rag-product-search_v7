"""สร้างไฟล์ให้ **คนที่สอง** ติดป้ายซ้ำ เพื่อวัดความน่าเชื่อถือของป้าย

ตามหลักการติดป้าย (Pustejovsky & Stubbs 2012) ป้ายที่มาจากคนเดียวใช้อ้างอิงไม่ได้
ต้องมีคนที่สองติดซ้ำส่วนหนึ่ง แล้วรายงานค่าความสอดคล้อง

⚠ **สุ่มแบบธรรมดา ไม่แบ่งโควตาตามป้าย** — ถ้าแบ่งโควตาให้ป้ายหายาก (เช่น 1)
มีสัดส่วนมากกว่าความจริง ค่า κ ที่ได้จะไม่ใช่ค่าของกองจริง เพราะ κ ขึ้นกับ
การกระจายของป้ายด้วย · ผลข้างเคียงคือป้ายหายากอาจติดมาน้อย ต้องรายงานไว้

⚠ **ปิดตาคนที่สอง** — ไฟล์ไม่มีป้ายของคนแรก ไม่มีคอลัมน์ แขน รอบ อันดับ คะแนน
  ชั้นความยาก และเรียงสลับใหม่ด้วยเมล็ดสุ่มคนละตัวกับไฟล์เดิม
  (ถ้าเรียงเหมือนเดิม คนที่สองอาจเดาได้ว่าของกลุ่มไหนมาด้วยกัน)

รัน:  python eval\\make_check_set.py
      python eval\\make_check_set.py --frac 0.3
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "eval" / "labels"
SOURCES = [LAB / "labels_a.csv", LAB / "labels_a2.csv"]
SEED = 777                      # คนละเมล็ดกับไฟล์เดิม
FIELDS = ["pair_id", "qid", "query", "product_title", "category",
          "price", "store", "details", "label", "note"]


def rel(path: Path) -> str:
    """ชื่อไฟล์แบบสั้น — ทนทานเมื่อผู้ใช้ส่ง path แบบ relative เข้ามา"""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="สร้างกองให้คนที่สองติดป้ายซ้ำ")
    ap.add_argument("--frac", type=float, default=0.20, help="สัดส่วนที่สุ่ม")
    ap.add_argument("--out", type=Path, default=LAB / "labels_a_check.csv")
    # ⚠ ต้องเลือกกองต้นทางได้ — กองที่ Claude ติด (`labels_a4.csv`) ต้องถูกตรวจ
    # ด้วยกองของตัวเอง ไม่ปนกับกองที่ผู้ใช้ติดเอง ไม่งั้น κ จะวัดคนละเรื่อง
    ap.add_argument("--from", dest="srcs", nargs="+", type=Path, default=None,
                    help="ไฟล์ป้ายต้นทางที่จะสุ่ม (ไม่ระบุ = labels_a.csv + labels_a2.csv)")
    args = ap.parse_args()

    sources = [LAB / s.name if s.parent == Path(".") else s
               for s in (args.srcs or SOURCES)]
    rows = []
    for src in sources:
        if not src.exists():
            continue
        with src.open(encoding="utf-8-sig", newline="") as fh:
            rows += [r for r in csv.DictReader(fh) if r["label"].strip()]
    n = round(len(rows) * args.frac)
    print(f"ป้ายของคนแรกทั้งหมด {len(rows)} คู่ · สุ่มมา {n} คู่ ({args.frac:.0%})")

    pick = random.Random(SEED).sample(rows, n)
    pick.sort(key=lambda r: (r["qid"], r["pair_id"]))   # เรียงตามคำค้น อ่านง่าย

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in pick:
            w.writerow({k: ("" if k in ("label", "note") else r.get(k, ""))
                        for k in FIELDS})

    from collections import Counter
    truth = Counter(r["label"] for r in pick)
    print(f"เขียน {rel(args.out)}")
    print(f"  ครอบคลุม {len({r['qid'] for r in pick})} คำค้น")
    print(f"  (ป้ายของคนแรกในกองนี้ — **ห้ามบอกคนที่สอง**) {dict(sorted(truth.items()))}")
    rare = [k for k in ("3", "2", "1", "0") if truth.get(k, 0) < 5]
    if rare:
        print(f"  ⚠ ป้าย {rare} ติดมาน้อยกว่า 5 คู่ -> κ ของชั้นนั้นไม่เสถียร ต้องรายงาน")
    print(f"\nขั้นตอน")
    print(f"  1. ส่ง {args.out.name} + docs/labelling_guide.md ให้คนที่สอง")
    print(f"  2. ให้เขากรอกคอลัมน์ label อย่างเดียว (3/2/1/0)")
    print(f"  3. python eval\\kappa.py {rel(args.out)}")


if __name__ == "__main__":
    main()
