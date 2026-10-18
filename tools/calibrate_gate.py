"""ขั้นที่ 5.4 — หาค่าเกณฑ์ประตูของ Reranker จากข้อมูล

**ประตู (ชั้นที่ 2 ของ Reranker) ต้องตอบคำถามสัมบูรณ์ว่า "มีของตรงไหม"**
ไม่ใช่คำถามเปรียบเทียบว่า "อันไหนตรงกว่า" → ต้องมีค่าเกณฑ์ และค่านั้นต้องมาจากข้อมูล

`src/rerank.py` ตั้งไว้ชั่วคราวที่ 0.60 ซึ่ง **ตัดอะไรไม่ได้เลย**
(รัน "wireless bluetooth earbuds" ผ่าน 73/73) เพราะคะแนนของ bge-m3 อยู่ในช่วงแคบ

**วิธีหา:** ต้องมีทั้งตัวอย่างที่ควรผ่านและที่ควรตก

    ควรผ่าน : คำค้นสินค้าจริง 40 คู่ (TEST + TEST2)
    ควรตก   : คำค้นที่ไม่มีของในคลัง 12 คำ (OOD_QUERIES) — บริการ คำปรึกษา ข้อมูล

**เกณฑ์ตัดสินค่าที่ดี** — ไล่ค่าประตูแล้วดู 2 อย่างพร้อมกัน

    1. ปล่อยของนอกคลังผ่านน้อยสุด   (ยิ่งประตูสูง ยิ่งดี)
    2. คำค้นสินค้าจริงยังเหลือของพอ  (ยิ่งประตูสูง ยิ่งแย่)

→ เลือกค่าที่สูงที่สุดที่คำค้นสินค้าจริงยังเหลือของครบตามต้องการ

⚠ **สิ่งที่ประตูทำไม่ได้:** แยก "เสื่อโยคะ" จาก "สายรัดเสื่อโยคะ" — ทั้งคู่เป็นของในคลัง
คะแนนใกล้กัน (ต่างกัน 0.03) เรื่องนั้นเป็นหน้าที่ของน้ำหนักในชั้นที่ 3 และทาง ข (คำหลัก)
ประตูตอบแค่ "คำค้นนี้มีของในคลังไหม"

รัน:  python tools\\calibrate_gate.py [--k 100] [--need 3]
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.queries import OOD_QUERIES, TEST2_PAIRS, TEST_PAIRS    # noqa: E402
from retrieval import Retriever                                  # noqa: E402

GATES = [round(0.50 + 0.01 * i, 2) for i in range(26)]           # 0.50 ถึง 0.75


def main() -> None:
    ap = argparse.ArgumentParser(description="หาค่าเกณฑ์ประตูจากข้อมูล")
    ap.add_argument("--k", type=int, default=100, help="ดึงผู้เข้าชิงกี่ชิ้น")
    ap.add_argument("--need", type=int, default=3,
                    help="คำค้นสินค้าจริงต้องเหลือของผ่านประตูอย่างน้อยกี่ชิ้น")
    args = ap.parse_args()

    in_domain = TEST_PAIRS + TEST2_PAIRS

    # ค้นด้วย **คำค้นอังกฤษที่คนเขียน** เพื่อตัดผลของชั้นแปลออกไป
    # (ถ้าใช้คำค้นไทย ค่าประตูที่ได้จะปนกับคุณภาพการแปล)
    print(f"ดึงผู้เข้าชิง {args.k} ชิ้นต่อคำค้น · "
          f"สินค้าจริง {len(in_domain)} คำ · นอกคลัง {len(OOD_QUERIES)} คำ\n")

    with Retriever() as r:
        pos = {p["id"]: [h.score for h in r.search(p["en"], k=args.k)]
               for p in in_domain}
        neg = {q["id"]: [h.score for h in r.search(q["en"], k=args.k)]
               for q in OOD_QUERIES}

    pos_top = {k: v[0] for k, v in pos.items()}
    neg_top = {k: v[0] for k, v in neg.items()}

    print("คะแนนอันดับ 1 — สองกลุ่มแยกกันแค่ไหน")
    print(f"  สินค้าจริง  ต่ำสุด {min(pos_top.values()):.3f} · "
          f"กลาง {st.median(pos_top.values()):.3f} · สูงสุด {max(pos_top.values()):.3f}")
    print(f"  นอกคลัง     ต่ำสุด {min(neg_top.values()):.3f} · "
          f"กลาง {st.median(neg_top.values()):.3f} · สูงสุด {max(neg_top.values()):.3f}")

    overlap = [i for i, s in pos_top.items() if s <= max(neg_top.values())]
    print(f"  เหลื่อมกัน: คำค้นสินค้าจริง {len(overlap)}/{len(pos_top)} คำ "
          f"มีคะแนนอันดับ 1 ต่ำกว่าคำค้นนอกคลังที่สูงสุด")
    if overlap:
        print(f"    {', '.join(overlap)}")

    worst_neg = max(neg_top, key=lambda k: neg_top[k])
    print(f"  คำนอกคลังที่คะแนนสูงสุด: {worst_neg} = {neg_top[worst_neg]:.3f}")

    # ---------------- ไล่ค่าประตู ----------------
    print(f"\n{'ประตู':>7} {'ของนอกคลังที่ผ่าน':>18} {'คำนอกคลังที่ยังผ่าน':>20}"
          f" {'คำค้นสินค้าที่เหลือ>=' + str(args.need):>24} {'ของที่เหลือเฉลี่ย':>18}")
    print("-" * 92)

    best = None
    for gate in GATES:
        neg_items = sum(1 for v in neg.values() for s in v if s >= gate)
        neg_queries = sum(1 for v in neg.values() if any(s >= gate for s in v))
        pos_ok = sum(1 for v in pos.values()
                     if sum(1 for s in v if s >= gate) >= args.need)
        pos_mean = st.mean(sum(1 for s in v if s >= gate) for v in pos.values())

        mark = ""
        if neg_queries == 0 and best is None:
            best = gate
            mark = "  <- ค่าต่ำสุดที่ตัดของนอกคลังได้หมด"
        print(f"{gate:>7.2f} {neg_items:>18,} {neg_queries:>18}/{len(neg)}"
              f" {pos_ok:>22}/{len(pos)} {pos_mean:>18.1f}{mark}")

    # ---------------- สรุป ----------------
    print(f"\n{'=' * 92}")
    if best is None:
        print("⚠ ไม่มีค่าประตูใดในช่วงที่ลองที่ตัดของนอกคลังได้ทั้งหมด")
        print("  -> ประตูค่าเดียวแยกไม่ได้ ต้องใช้สัญญาณอื่นช่วย (เช่น คะแนนอันดับ 1)")
    else:
        pos_ok = sum(1 for v in pos.values()
                     if sum(1 for s in v if s >= best) >= args.need)
        lost = [i for i, v in pos.items()
                if sum(1 for s in v if s >= best) < args.need]
        print(f"ค่าต่ำสุดที่ตัดคำค้นนอกคลังได้ทั้ง {len(neg)} คำ: **{best:.2f}**")
        print(f"ที่ค่านี้ คำค้นสินค้าจริงยังเหลือของ >= {args.need} ชิ้น "
              f"{pos_ok}/{len(pos)} คำ")
        if lost:
            print(f"คำค้นสินค้าจริงที่เสียไป: {', '.join(lost)}")
            print("  -> ตรวจด้วยตาว่าเป็นคำค้นที่คลังไม่มีของจริง หรือประตูสูงเกินไป")

    print("\nหมายเหตุ: ประตูตอบแค่ 'คำค้นนี้มีของในคลังไหม'")
    print("          แยก 'เสื่อโยคะ' จาก 'สายรัดเสื่อ' ไม่ได้ — นั่นเป็นงานของชั้นที่ 3")


if __name__ == "__main__":
    main()
