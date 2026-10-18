"""ขั้นที่ 5.2 — ทดสอบว่าชั้นแปลภาษาแก้ปัญหาค้นภาษาไทยได้จริงไหม

**เกณฑ์ตัดสิน:** ขั้นที่ 4.4 วัดไว้ว่าค้นด้วยไทยตรง ๆ ได้ผลทับซ้อนกับฝั่งอังกฤษ
**25.3%** ถ้าชั้นแปลทำงาน ตัวเลขนี้ต้องขึ้นไปใกล้ 100%

วัด 3 ทางกับคำค้นคู่เดียวกัน 15 คู่ (ชุดเดียวกับ `test_bilingual.py`):

    ก. ค้นด้วยไทยตรง ๆ          -> เทียบกับ ค   (ของเดิม)
    ข. ค้นด้วยไทยที่แปลแล้ว     -> เทียบกับ ค   (ของใหม่)
    ค. ค้นด้วยอังกฤษที่คนเขียน  -> **เกณฑ์อ้างอิง**

⚠ overlap วัด **ความสอดคล้อง** ไม่ใช่ **ความถูกต้อง** — ถ้าฝั่งอังกฤษค้นผิดอยู่แล้ว
overlap สูงก็แปลว่าผิดเหมือนกันทั้งคู่ จึงพิมพ์คำแปลและชื่อสินค้าออกมาให้อ่านด้วยตาเสมอ

รัน:  python tools\\test_translate.py [--k 5]
⚠ ต้องสตาร์ต Ollama ก่อน (ใช้ทั้ง bge-m3 และ Typhoon)
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from retrieval import Retriever                                   # noqa: E402
from test_bilingual import PAIRS                                  # noqa: E402
from translate import (_clean_output, clear_cache, detect_language,  # noqa: E402
                       prepare_query, thai_ratio, translate)

PASS = FAIL = 0


def check(name: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          ได้   {got!r}\n          ควรได้ {want!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description="ทดสอบชั้นแปลภาษา")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    # -----------------------------------------------------------------------
    print("\n[1] ตรวจภาษา — ไม่เรียก LLM")
    # -----------------------------------------------------------------------
    check("ไทยล้วน", detect_language("เสื่อโยคะกันลื่น"), "th")
    check("อังกฤษล้วน", detect_language("non-slip yoga mat"), "en")
    check("ไทยผสมอังกฤษ -> ถือเป็นไทย", detect_language("เคส iPhone 15"), "th")
    check("ตัวเลขล้วน -> อังกฤษ", detect_language("12345"), "en")
    check("ว่างเปล่า -> อังกฤษ", detect_language(""), "en")
    check("สัดส่วนไทยของคำไทยล้วน", thai_ratio("เสื่อโยคะ"), 1.0)
    check("สัดส่วนไทยของคำอังกฤษล้วน", thai_ratio("yoga mat"), 0.0)

    print("\n[2] ล้างผลลัพธ์ที่โมเดลตอบมา")
    check("ตัดเครื่องหมายคำพูด", _clean_output('"yoga mat"', "x"), "yoga mat")
    check("เอาบรรทัดแรก", _clean_output("yoga mat\nคำอธิบาย...", "x"), "yoga mat")
    check("ตัดคำนำหน้า", _clean_output("Translation: yoga mat", "x"), "yoga mat")
    check("ยังมีไทยอยู่ -> คืนของเดิม", _clean_output("เสื่อโยคะ", "ของเดิม"), "ของเดิม")
    check("ว่างเปล่า -> คืนของเดิม", _clean_output("   ", "ของเดิม"), "ของเดิม")
    check("ยาวเกินไป -> คืนของเดิม", _clean_output("x" * 300, "ของเดิม"), "ของเดิม")

    print("\n[3] จำคำแปลไว้ (cache)")
    clear_cache()
    plan1 = prepare_query("เสื่อโยคะกันลื่น")
    plan2 = prepare_query("เสื่อโยคะกันลื่น")
    check("รอบแรกเรียก LLM", plan1.used_llm, True)
    check("รอบสองไม่เรียกซ้ำ", plan2.used_llm, False)
    check("รอบสองมาจาก cache", plan2.from_cache, True)
    check("ได้คำแปลเดิม", plan1.search_text, plan2.search_text)
    check("คำถามอังกฤษไม่เรียก LLM", prepare_query("yoga mat").used_llm, False)

    # -----------------------------------------------------------------------
    print(f"\n[4] วัดผลจริง — คำค้น {len(PAIRS)} คู่ · เทียบ top-{args.k}")
    print("    (แปลครั้งแรกจะช้าเพราะต้องโหลด Typhoon เข้า GPU)\n")
    # -----------------------------------------------------------------------
    clear_cache()
    rows = []
    t0 = time.time()
    with Retriever() as r:
        print(f"{'':6} {'ไทยตรง ๆ':>10} {'ไทยแปลแล้ว':>12}   คำแปลที่โมเดลให้")
        print("-" * 78)
        for pair in PAIRS:
            plan = prepare_query(pair["th"])
            th_ids = [h.id for h in r.search(pair["th"], k=args.k)]
            tr_ids = [h.id for h in r.search(plan.search_text, k=args.k)]
            en_ids = [h.id for h in r.search(pair["en"], k=args.k)]

            ov_th = len(set(th_ids) & set(en_ids)) / args.k
            ov_tr = len(set(tr_ids) & set(en_ids)) / args.k
            rows.append({"pair": pair, "plan": plan, "ov_th": ov_th, "ov_tr": ov_tr})

            arrow = "↑" if ov_tr > ov_th else ("=" if ov_tr == ov_th else "↓")
            print(f"{pair['id']:6} {ov_th:>9.0%} {ov_tr:>11.0%} {arrow}  "
                  f"{plan.search_text[:44]}")

    secs = time.time() - t0
    mean_th = st.mean(r_["ov_th"] for r_ in rows)
    mean_tr = st.mean(r_["ov_tr"] for r_ in rows)
    better = sum(1 for r_ in rows if r_["ov_tr"] > r_["ov_th"])
    worse = sum(1 for r_ in rows if r_["ov_tr"] < r_["ov_th"])
    failed = [r_ for r_ in rows if r_["plan"].translated is None]

    print("\n" + "=" * 78)
    print(f"ทับซ้อน@{args.k} เฉลี่ย — ไทยตรง ๆ {mean_th:.1%}  ->  "
          f"ไทยแปลแล้ว {mean_tr:.1%}")
    print(f"ดีขึ้น {better} คู่ · เท่าเดิม {len(rows) - better - worse} คู่ · "
          f"แย่ลง {worse} คู่")
    print(f"แปลไม่สำเร็จ {len(failed)} คู่ · ใช้เวลาทั้งหมด {secs:.0f} วินาที")

    if failed:
        print("\nคู่ที่แปลไม่สำเร็จ (ค้นด้วยไทยไปก่อน):")
        for r_ in failed:
            print(f"  {r_['pair']['id']}  {r_['pair']['th']}")

    drops = sorted((r_ for r_ in rows if r_["ov_tr"] < r_["ov_th"]),
                   key=lambda x: x["ov_tr"] - x["ov_th"])
    if drops:
        print("\nคู่ที่แย่ลง — ดูว่าคำแปลเพี้ยนไหม:")
        for r_ in drops:
            print(f"  {r_['pair']['id']}  ไทย: {r_['pair']['th']}")
            print(f"        แปลได้: {r_['plan'].search_text}")
            print(f"        คนเขียน: {r_['pair']['en']}")

    print(f"\n{'=' * 78}")
    print(f"เทสต์หน่วย: ผ่าน {PASS} · ไม่ผ่าน {FAIL}")
    verdict = "✅ ชั้นแปลช่วยจริง" if mean_tr > mean_th + 0.15 else "⚠ ยังไม่ชัด ต้องดูรายคู่"
    print(f"ผลวัด: {verdict}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
