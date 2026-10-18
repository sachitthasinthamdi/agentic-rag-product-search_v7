"""ขั้นที่ 4.4 — ทดสอบว่าค้นด้วยภาษาไทยได้ผลเทียบเท่าภาษาอังกฤษไหม

**ทำไมต้องทดสอบ:** ข้อมูลสินค้าเป็นภาษาอังกฤษ 100% (ชื่อสินค้าที่มีอักษรไทย 0 แถว)
แต่ระบบต้องรับคำถามภาษาไทย ถ้าโมเดลข้ามภาษาได้ไม่ดี ต้องเพิ่มชั้นแปลภาษา
— **รู้ตรงนี้ก่อนไปขั้นที่ 5 ดีกว่ารู้ทีหลังตอนสร้าง agent เสร็จแล้ว**

**วิธีวัด:** ยิงคำค้นคู่ไทย-อังกฤษที่ความหมายเดียวกัน แล้วดูว่าได้สินค้าชุดเดียวกันไหม

⚠ ตัวเลขที่ได้คือ **ความสอดคล้อง (agreement)** ไม่ใช่ **ความถูกต้อง (correctness)**
ถ้าฝั่งอังกฤษค้นผิดอยู่แล้ว overlap สูงก็แปลว่าผิดเหมือนกันทั้งคู่
จึงพิมพ์ชื่อสินค้าออกมาให้อ่านด้วยตาประกอบเสมอ

รัน:  python tools\\test_bilingual.py [--k 10]
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from retrieval import Retriever   # noqa: E402

# คำค้นคู่ไทย-อังกฤษ — เลือกให้ตรงกับหมวดที่มีสินค้าเยอะในคลังจริง
# (เสื้อผ้า 37% · บ้านและครัว 14% · อิเล็กทรอนิกส์ · ยานยนต์ · กีฬา · สัตว์เลี้ยง)
PAIRS = [
    {"id": "q01", "th": "หูฟังบลูทูธไร้สายกันน้ำ", "en": "waterproof wireless bluetooth headphones"},
    {"id": "q02", "th": "เคสมือถือกันกระแทก", "en": "shockproof phone case"},
    {"id": "q03", "th": "รองเท้าวิ่งผู้ชายน้ำหนักเบา", "en": "lightweight running shoes for men"},
    {"id": "q04", "th": "เสื้อยืดผ้าฝ้ายสีดำ", "en": "black cotton t-shirt"},
    {"id": "q05", "th": "กระเป๋าสะพายข้างหนังผู้หญิง", "en": "women's leather crossbody bag"},
    {"id": "q06", "th": "กระทะเหล็กหล่อ", "en": "cast iron skillet"},
    {"id": "q07", "th": "หมอนหนุนเมมโมรี่โฟม", "en": "memory foam pillow"},
    {"id": "q08", "th": "ผ้าม่านกันแสงห้องนอน", "en": "blackout curtains for bedroom"},
    {"id": "q09", "th": "ชุดไขควงอเนกประสงค์", "en": "multipurpose screwdriver set"},
    {"id": "q10", "th": "ที่ชาร์จในรถยนต์", "en": "car charger"},
    {"id": "q11", "th": "ใบปัดน้ำฝนรถยนต์", "en": "car windshield wiper blades"},
    {"id": "q12", "th": "เสื่อโยคะกันลื่น", "en": "non-slip yoga mat"},
    {"id": "q13", "th": "ดัมเบลปรับน้ำหนักได้", "en": "adjustable dumbbell"},
    {"id": "q14", "th": "ปลอกคอสุนัขปรับขนาดได้", "en": "adjustable dog collar"},
    {"id": "q15", "th": "เมาส์ไร้สายสำหรับเล่นเกม", "en": "wireless gaming mouse"},
]


def main() -> None:
    parser = argparse.ArgumentParser(description="ทดสอบค้นหาสองภาษา")
    parser.add_argument("--k", type=int, default=10, help="จำนวนผลลัพธ์ที่นำมาเทียบ")
    parser.add_argument("--show", type=int, default=3, help="แสดงชื่อสินค้ากี่อันดับ")
    args = parser.parse_args()

    with Retriever() as r:
        print(f"ดัชนีมี {r.count():,} รายการ · เทียบ top-{args.k} ของคำค้น {len(PAIRS)} คู่\n")

        rows = []
        for pair in PAIRS:
            th = r.search(pair["th"], k=args.k)
            en = r.search(pair["en"], k=args.k)
            th_ids = [h.id for h in th]
            en_ids = [h.id for h in en]

            rows.append({
                "id": pair["id"], "th": pair["th"], "en": pair["en"],
                "overlap5": len(set(th_ids[:5]) & set(en_ids[:5])) / 5,
                "overlapk": len(set(th_ids) & set(en_ids)) / args.k,
                "en_top1_in_th": en_ids[0] in th_ids,
                "th_score": st.fmean(h.score for h in th[:5]),
                "en_score": st.fmean(h.score for h in en[:5]),
                "th_hits": th[:args.show], "en_hits": en[:args.show],
            })
            print(f"  {pair['id']} {pair['th'][:30]:32s} overlap@5={rows[-1]['overlap5']:4.0%} "
                  f"· คะแนน ไทย {rows[-1]['th_score']:.3f} / อังกฤษ {rows[-1]['en_score']:.3f}")

        print("\n" + "=" * 90)
        print("สรุป")
        print("=" * 90)
        print(f"  overlap@5 เฉลี่ย                       {st.fmean(x['overlap5'] for x in rows):6.1%}")
        print(f"  overlap@{args.k} เฉลี่ย                      "
              f"{st.fmean(x['overlapk'] for x in rows):6.1%}")
        print(f"  อันดับ 1 ของอังกฤษ ติด top-{args.k} ของไทย   "
              f"{st.fmean(x['en_top1_in_th'] for x in rows):6.1%}")
        print(f"  คะแนนเฉลี่ย top-5 ฝั่งไทย                {st.fmean(x['th_score'] for x in rows):6.4f}")
        print(f"  คะแนนเฉลี่ย top-5 ฝั่งอังกฤษ             {st.fmean(x['en_score'] for x in rows):6.4f}")

        worst = sorted(rows, key=lambda x: x["overlap5"])[:4]
        print("\n" + "=" * 90)
        print("4 คำค้นที่สอดคล้องกันน้อยที่สุด — อ่านด้วยตาว่าฝั่งไหนถูก")
        print("=" * 90)
        for row in worst:
            print(f"\n{row['id']} ไทย: \"{row['th']}\"  ·  อังกฤษ: \"{row['en']}\"  "
                  f"(overlap@5 = {row['overlap5']:.0%})")
            for label, hits in (("ไทย    ", row["th_hits"]), ("อังกฤษ", row["en_hits"])):
                print(f"  {label}")
                for hit in hits:
                    print(f"     [{hit.score:.3f}] {hit.title[:72]}")


if __name__ == "__main__":
    main()
