"""ขั้นที่ 5.1 — ทดสอบ Reranker ทีละชั้น

ทดสอบ `src/rerank.py` ด้วยข้อมูลที่สร้างขึ้นเอง (ไม่ต้องมี Ollama หรือ Chroma)
แล้วปิดท้ายด้วยการรันกับข้อมูลจริงถ้ามีดัชนีอยู่

**ทำไมต้องเทสต์:** ชั้นที่ 3 เป็นสูตรที่ผลลัพธ์ดูด้วยตาไม่ออกว่าถูกหรือผิด
และ `rank_descending` มีกรณีขอบที่พลาดง่าย (NaN เป็นจริงใน Python)

รัน:  python tools\\test_rerank.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rerank import (RRF_K, Constraints, apply_gate, apply_rules,  # noqa: E402
                    order_by_votes, pick_diverse, rank_descending, rerank)
from retrieval import Hit                                          # noqa: E402

PASS = FAIL = 0


def check(name: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok    {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          ได้   {got}\n          ควรได้ {want}")


def check_true(name: str, cond: bool) -> None:
    check(name, bool(cond), True)


def mk(id_: str, score: float, price: float | None = 10.0,
       rating: float | None = 4.5, n_reviews: int | None = 100,
       store: str | None = "ร้าน A", category: str = "Electronics",
       title: str | None = None) -> Hit:
    """สร้าง Hit ปลอมสำหรับเทสต์

    ชั้น 3 อ่าน `rating` กับ `n_reviews` **จากฟิลด์ของ Hit ตรง ๆ**
    (เดิมอ่าน popularity/value_score จาก metadata — เลิกใช้แล้วตามที่อาจารย์กำหนด)
    """
    return Hit(id=id_, score=score, title=title or f"สินค้า {id_}",
               category=category, price=price, rating=rating,
               n_reviews=n_reviews, popularity=None, store=store,
               metadata={"store": store, "price": price})


# ---------------------------------------------------------------------------
print("\n[1] rank_descending — ค่ามาก = อันดับดี")
# ---------------------------------------------------------------------------
check("เรียงปกติ", rank_descending([3, 1, 2]), [1, 3, 2])
check("ค่าเท่ากันได้อันดับเดียวกัน (1,1,3)", rank_descending([5, 5, 1]), [1, 1, 3])
check("None อยู่ท้ายสุด", rank_descending([2, None, 1]), [1, 3, 2])
check("NaN อยู่ท้ายสุด (NaN != NaN)", rank_descending([2, float("nan"), 1]), [1, 3, 2])
check("หายหมดทุกตัว -> ท้ายสุดร่วมกัน", rank_descending([None, None]), [1, 1])
check("รายการว่าง", rank_descending([]), [])

# ---------------------------------------------------------------------------
print("\n[2] ชั้น 1 — กฎตัดของที่ผิดเงื่อนไข")
# ---------------------------------------------------------------------------
hits = [mk("a", 0.7, price=20.0), mk("b", 0.7, price=50.0), mk("c", 0.7, price=None)]
check("ไม่มีเงื่อนไข -> ไม่ตัดอะไร", len(apply_rules(hits, Constraints())), 3)
check("งบ $30 ตัดของแพง", [h.id for h in apply_rules(hits, Constraints(budget_max=30))],
      ["a"])
check_true("ของไม่มีราคาถูกตัดเมื่อมีงบ",
           "c" not in [h.id for h in apply_rules(hits, Constraints(budget_max=100))])

# หมวดเปลี่ยนจาก "ตัวกรอง" เป็น "สัญญาณในชั้น 3" ตามที่อาจารย์กำหนด
# ของนอกหมวดต้องยังอยู่ครบ ไม่ถูกตัดทิ้ง
hits2 = [mk("a", 0.7, category="Electronics"), mk("b", 0.7, category="Pet Supplies")]
check("หมวดไม่ตัดอะไรทิ้งแล้ว",
      [h.id for h in apply_rules(hits2, Constraints(category="Pet Supplies"))],
      ["a", "b"])

hits3 = [mk("a", 0.7, store="Sony"), mk("b", 0.7, store="JBL")]
check("ตัดร้านที่ไม่เอา (ไม่สนตัวพิมพ์)",
      [h.id for h in apply_rules(hits3, Constraints(stores_excluded=["sony"]))], ["b"])

hits4 = [mk("a", 0.7, title="หูฟัง XYZ รุ่นใหม่"), mk("b", 0.7, title="ลำโพง ABC")]
check("ตัดของที่ผู้ใช้ปฏิเสธแล้ว (เทียบแบบมีอยู่ในชื่อ)",
      [h.id for h in apply_rules(hits4, Constraints(titles_rejected=["หูฟัง XYZ"]))], ["b"])

# ---------------------------------------------------------------------------
print("\n[3] ชั้น 2 — ประตูความตรง")
# ---------------------------------------------------------------------------
hits5 = [mk("a", 0.70), mk("b", 0.60), mk("c", 0.59)]
check("ตัดที่ต่ำกว่าเกณฑ์ (เท่ากับเกณฑ์ = ผ่าน)",
      [h.id for h in apply_gate(hits5, 0.60)], ["a", "b"])
check("เกณฑ์สูงจนไม่มีใครผ่าน", apply_gate(hits5, 0.99), [])

# ---------------------------------------------------------------------------
print("\n[4] ชั้น 3 — เรียงแบบโหวต")
# ---------------------------------------------------------------------------
# ของที่ตรงน้อยกว่าแต่รีวิวและความคุ้มดีกว่า ควรแพ้เมื่อความตรงมีน้ำหนัก
near = mk("ตรงน้อย_ดัง", 0.65, rating=5.0, n_reviews=9999)
best = mk("ตรงมาก_ไม่ดัง", 0.70, rating=1.0, n_reviews=1)
order_w0 = [r.hit.id for r in order_by_votes([near, best], w_relevance=0)]
order_w3 = [r.hit.id for r in order_by_votes([near, best], w_relevance=3)]
check("น้ำหนัก 0 -> ของที่ไม่ค่อยตรงชนะ (ข้อบกพร่องที่ต้องแก้)",
      order_w0[0], "ตรงน้อย_ดัง")
check("น้ำหนัก 3 -> ของที่ตรงชนะ", order_w3[0], "ตรงมาก_ไม่ดัง")

ranked = order_by_votes([near, best])
check("อันดับความตรงถูกบันทึกไว้", ranked[0].rank_relevance, 1)
check_true("มีเหตุผลติดมาด้วย", "ความตรง #1" in ranked[0].why())

# ⚠ ข้อจำกัดที่วัดได้: น้ำหนัก 3 ไม่พอสำหรับกรณีสุดขั้ว
# A อยู่อันดับความตรงที่ 10 แต่เป็นที่ 1 ทั้งรีวิวและความคุ้ม
# B อยู่อันดับความตรงที่ 1 แต่เป็นที่ 20 ทั้งคู่ -> ต้องใช้น้ำหนัก >= 3.70 B จึงชนะ
# ใส่แค่ 3 เทอมพอ เพราะกรณีนี้ทั้งสองชิ้นอยู่หมวดเดียวกัน
# สัญญาณที่ 4 (ตรงหมวด) จึงเท่ากันและหักล้างกันไปเอง
def votes(w, r_rel, r_rat, r_rev):
    return w / (RRF_K + r_rel) + 1 / (RRF_K + r_rat) + 1 / (RRF_K + r_rev)

check_true("กรณีสุดขั้ว: น้ำหนัก 3 ยังไม่พอ (ของที่ไม่ตรงชนะ)",
           votes(3, 10, 1, 1) > votes(3, 1, 20, 20))
check_true("กรณีสุดขั้ว: น้ำหนัก 3.7 พอ",
           votes(3.7, 1, 20, 20) > votes(3.7, 10, 1, 1))

# -- สัญญาณที่ 4: ตรงหมวดกับโปรไฟล์ผู้ใช้ --------------------------------------
# ของนอกหมวดต้องถูกดันลง แต่ไม่ถูกตัดทิ้ง
cat_hits = [mk("นอกหมวด", 0.70, category="Pet Supplies"),
            mk("ในหมวด", 0.68, category="Electronics")]
check("ไม่ระบุหมวด -> เรียงตามความตรง",
      [r.hit.id for r in order_by_votes(cat_hits)], ["นอกหมวด", "ในหมวด"])
check("ของนอกหมวดยังอยู่ ไม่ถูกตัดทิ้ง",
      len(order_by_votes(cat_hits, wanted_category="Electronics")), 2)
check("หมวดที่ไม่มีในกอง -> ทุกชิ้นเสมอกัน สัญญาณเงียบ",
      [r.hit.id for r in order_by_votes(cat_hits, wanted_category="Books")],
      [r.hit.id for r in order_by_votes(cat_hits)])

# ⚠ ขีดจำกัดที่วัดแล้ว — ในกอง 2 ชิ้น สัญญาณหมวดมีแค่ 2 อันดับ (1 กับ 2)
# ส่วนต่างคะแนนจึงแค่ 0.00026 ชดเชยความตรงที่ห่างกัน 1 อันดับ (0.00079) ไม่ได้
check("กองเล็ก -> ตรงหมวดยังพลิกความตรงไม่ได้ (ขีดจำกัดที่รับทราบ)",
      [r.hit.id for r in order_by_votes(cat_hits, wanted_category="Electronics")][0],
      "นอกหมวด")

# กองจริงมี 100 ชิ้น ของนอกหมวดได้อันดับท้ายกลุ่ม ส่วนต่างจึงใหญ่พอจะพลิกได้
# 100 ชิ้นเรียงความตรงลงมา · ของในหมวดอยู่อันดับความตรงที่ 4-33
# (ของนอกหมวด 3 ชิ้นแรกตรงกว่าเล็กน้อย ซึ่งเป็นภาพที่เจอจริงในกองผู้เข้าชิง)
pool = [mk(f"p{i}", 0.70 - i * 0.001,
           category="Electronics" if 3 <= i < 33 else "Pet Supplies")
        for i in range(100)]
top = order_by_votes(pool, wanted_category="Electronics")[0]
check("กองจริง 100 ชิ้น -> ของในหมวดขึ้นอันดับ 1 แม้ความตรงต่ำกว่า",
      top.hit.category, "Electronics")
check("อันดับหมวดถูกบันทึกไว้", top.rank_category, 1)

# เพดานของสัญญาณนี้ — ชดเชยได้ราว 5 อันดับความตรง ไม่ใช่ไม่จำกัด
def votes4(r_rel, r_cat):
    return 3 / (RRF_K + r_rel) + 1 / (RRF_K + 1) + 1 / (RRF_K + 1) + 1 / (RRF_K + r_cat)

check_true("ตรงหมวดชดเชยความตรงที่ห่าง 5 อันดับได้",
           votes4(6, 1) > votes4(1, 31))
check_true("แต่ห่าง 10 อันดับชดเชยไม่ได้",
           votes4(11, 1) < votes4(1, 31))

# -- ดาวคู่กับจำนวนรีวิว แทนสูตรเบย์สเดิม ----------------------------------------
# ของ 5 ดาวรีวิวเดียวต้องไม่ชนะของ 4.8 ดาวรีวิวเยอะ เมื่อความตรงเท่ากัน
one_review = mk("5ดาว_รีวิวเดียว", 0.70, rating=5.0, n_reviews=1)
many_review = mk("4.8ดาว_สองพัน", 0.70, rating=4.8, n_reviews=2000)
check("ดาวดิบอย่างเดียวไม่พอ -> จำนวนรีวิวถ่วงไว้",
      [r.hit.id for r in order_by_votes([one_review, many_review])][0],
      "4.8ดาว_สองพัน")

# คะแนนเท่ากันต้องให้ผลเดิมทุกครั้ง ไม่ขึ้นกับลำดับที่รับเข้ามา
same = [mk("z", 0.7), mk("y", 0.7), mk("x", 0.7)]
check("คะแนนเท่ากัน -> เรียงนิ่ง (ตาม id)",
      [r.hit.id for r in order_by_votes(same)],
      [r.hit.id for r in order_by_votes(list(reversed(same)))])

# ---------------------------------------------------------------------------
print("\n[5] ชั้น 4 — กันร้านซ้ำ")
# ---------------------------------------------------------------------------
dup = order_by_votes([mk("a", 0.70, store="ร้าน X"), mk("b", 0.69, store="ร้าน X"),
                      mk("c", 0.68, store="ร้าน Y"), mk("d", 0.67, store="ร้าน Z")])
picked, skipped = pick_diverse(dup, n=3)
check("ไม่เอาร้านซ้ำ", [h.id for h in picked], ["a", "c", "d"])
check("นับที่ข้ามไว้", skipped, 1)

only_one = order_by_votes([mk("a", 0.70, store="ร้าน X"), mk("b", 0.69, store="ร้าน X")])
picked2, _ = pick_diverse(only_one, n=3)
check("ของไม่พอ -> เติมที่ร้านซ้ำกลับเข้าไป", [h.id for h in picked2], ["a", "b"])

# ---------------------------------------------------------------------------
print("\n[6] rerank() ทั้ง 4 ชั้นต่อกัน")
# ---------------------------------------------------------------------------
pool = [mk("แพงเกิน", 0.73, price=99.0),
        mk("ไม่ตรง", 0.50, price=10.0),
        mk("ดี1", 0.70, price=10.0, store="ร้าน A", rating=4.9, n_reviews=900),
        mk("ดี2", 0.69, price=12.0, store="ร้าน A", rating=4.8, n_reviews=800),
        mk("ดี3", 0.68, price=15.0, store="ร้าน B", rating=4.7, n_reviews=700),
        mk("ดี4", 0.67, price=18.0, store="ร้าน C", rating=4.6, n_reviews=600)]
res = rerank(pool, Constraints(budget_max=30))
check("เข้ามากี่ชิ้น", res.n_candidates, 6)
check("ชั้น 1 ตัดของแพงออก", res.n_after_rules, 5)
check("ชั้น 2 ตัดของที่ไม่ตรงออก -> n_passed", res.n_passed, 4)
check("ได้ 3 ชิ้น", len(res.picked), 3)
check("ไม่มีร้านซ้ำในผลลัพธ์",
      len({h.store for h in res.picked}), len(res.picked))
check_true("enough() บอกว่าพอ", res.enough())
check_true("trace() มี n_passed ให้ Planner อ่าน", res.trace()["n_passed"] == 4)

empty = rerank([mk("ไม่ตรงเลย", 0.30)], Constraints())
check("ไม่มีใครผ่านประตู -> n_passed = 0", empty.n_passed, 0)
check_true("enough() บอกว่าไม่พอ -> ลูปต้องค้นใหม่", not empty.enough())
check("ไม่มีผู้เข้าชิงเลยก็ไม่พัง", rerank([]).n_passed, 0)

# ---------------------------------------------------------------------------
print("\n[7] รันกับข้อมูลจริง (ข้ามได้ถ้าไม่มีดัชนีหรือ Ollama)")
# ---------------------------------------------------------------------------
try:
    from retrieval import Retriever
    with Retriever() as r:
        real = r.search("wireless bluetooth earbuds", k=100)
    out = rerank(real, Constraints(budget_max=30))
    check("ดึงมา 100 ชิ้น", out.n_candidates, 100)
    check_true("ชั้น 1 ตัดของเกินงบจริง", out.n_after_rules < out.n_candidates)
    check_true("ทุกชิ้นที่เลือกอยู่ในงบ",
               all(h.price <= 30 for h in out.picked))
    check_true("ไม่มีร้านซ้ำ", len({h.store for h in out.picked}) == len(out.picked))
    check("เรียกซ้ำได้ผลเดิม",
          [h.id for h in rerank(real, Constraints(budget_max=30)).picked],
          [h.id for h in out.picked])
    print(f"\n  ผ่านประตู {out.n_passed}/{out.n_after_rules} ชิ้น · "
          f"ข้ามเพราะร้านซ้ำ {out.n_skipped_duplicate} ชิ้น")
    for n, rk in enumerate(out.ranked[:3], 1):
        print(f"    {n}. {rk.hit.title[:52]}")
        print(f"       ${rk.hit.price:.2f} · {rk.why()}")
except SystemExit as exc:
    print(f"  ข้าม — {exc}")
except Exception as exc:                                   # noqa: BLE001
    print(f"  ข้าม — {type(exc).__name__}: {str(exc)[:70]}")

# ---------------------------------------------------------------------------
print(f"\n{'=' * 60}")
print(f"ผ่าน {PASS} · ไม่ผ่าน {FAIL}")
sys.exit(1 if FAIL else 0)
