"""ชั้นที่ 4 — Reranker

รับผู้เข้าชิงจาก `search()` แล้วคัดเหลือไม่กี่ชิ้นเพื่อส่งให้ Generator

**คืนผลลัพธ์ 3 อย่าง ไม่ใช่อย่างเดียว:**

  1. `picked`     — ไม่กี่ชิ้นที่เลือกแล้ว (ส่งให้ Generator)
  2. `ranked`     — ทุกชิ้นที่ผ่านประตู เรียงลำดับแล้ว พร้อมเหตุผล
  3. `n_passed`   — **ผ่านประตูกี่ชิ้น** ← Planner ของ A3/A4 ใช้ตัดสินว่าจะค้นซ้ำไหม

ข้อ 3 เป็นของที่ A2 (pipeline) ไม่มี และเป็นสิ่งที่ทำให้ลูปของ A3/A4 ทำงานได้
เพราะ **ลำดับเป็นเกณฑ์เปรียบเทียบ แต่ "ดีพอหรือยัง" ต้องเป็นเกณฑ์สัมบูรณ์** —
ของที่แย่ที่สุดใน 100 ชิ้นก็ยังได้อันดับ 100 อยู่ดี ลำดับไม่เคยบอกว่า "ทั้งกองไม่ตรงเลย"

**คัดเป็นชั้น (cascade) 4 ชั้น — ไม่รวมเป็นสูตรเดียว:**

    ชั้น 1  ตัดของที่ผิดเงื่อนไขที่ผู้ใช้บอกเอง   (งบ / หมวด / ร้าน / ของที่ปฏิเสธแล้ว)
    ชั้น 2  ประตูความตรง: ต่ำกว่าเกณฑ์ = ตก        ◀── n_passed เกิดที่นี่
    ชั้น 3  เรียงแบบโหวต ความตรง:รีวิว:ความคุ้ม = 3:1:1
    ชั้น 4  หยิบ N ชิ้น ห้ามร้านซ้ำ

ที่แยกเป็นชั้นเพราะถ้ารวมเป็นคะแนนเดียว **ของที่ไม่ตรงจะชนะได้** — ลำโพงบลูทูธที่
รีวิว 4.9 จาก 5,000 คน จะแซงหูฟังที่รีวิว 4.2 จาก 80 คน ทั้งที่ผู้ใช้ขอหูฟัง

**ทำไมไม่ใช้ LLM:** mark5 วัด LLM-as-judge ด้วย 4 พรอมต์ ได้ Cohen's κ = 0.08-0.25
ซึ่งเป็นงานเดียวกันเป๊ะกับที่ Reranker ต้องทำ · และวิทยานิพนธ์ต้องวัดว่า "ลูปช่วยไหม"
ถ้า Reranker เหวี่ยง จะแยกไม่ออกว่าผลดีขึ้นเพราะลูปหรือเพราะความเหวี่ยง
→ ไฟล์นี้ **เรียก LLM 0 ครั้ง และให้ผลเดิมทุกครั้ง**

**สิ่งที่ไฟล์นี้จงใจไม่รู้:** ใครเรียก · เรียกกี่รอบ · ใครตัดสินว่าจะค้นซ้ำ —
เหมือน `retrieval.py` คือใช้ร่วมกันได้ทุกสถาปัตยกรรม (A1 กับ A3 ต้องใช้ตัวเดียวกันเป๊ะ
ไม่งั้นผลเทียบจะปนกัน)

รายละเอียดการตัดสินใจและหลักฐานทั้งหมดอยู่ใน `docs/reranker_plan.md`
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval import Hit                                        # noqa: E402

# ---------------------------------------------------------------------------
# ค่าตั้ง
# ---------------------------------------------------------------------------

N_PICK = 3                  # ส่งให้ Generator กี่ชิ้น

# ค่าประตู — หามาจากข้อมูลแล้ว (ขั้น 5.4 · tools/calibrate_gate.py)
#
# ประตูตอบคำถามสัมบูรณ์ว่า **"คลังมีของประเภทนี้ไหม"** ไม่ใช่ "ชิ้นนี้ดีไหม"
#
# วิธีหา: ค้นด้วยคำค้นสินค้าจริง 40 คำ (TEST+TEST2) เทียบกับคำค้นที่ไม่มีของในคลัง
# 12 คำ (OOD_QUERIES — บริการ คำปรึกษา ข้อมูล) แล้วดูคะแนนอันดับ 1
#
#   สินค้าจริง   0.565 - 0.751  (กลาง 0.689)
#   นอกคลัง      0.425 - 0.539  (กลาง 0.480)
#   **ไม่เหลื่อมกันเลย** — ช่องว่างระหว่างสองกลุ่ม 0.539 ถึง 0.565
#
# 0.54 เป็นค่าต่ำสุดที่ตัดคำค้นนอกคลังได้ทั้ง 12 คำ
# **เลือก 0.55 เพราะเป็นกลางช่องว่าง** → มีระยะเผื่อทั้งสองด้าน (มีตัวอย่างนอกคลังแค่ 12 คำ
# ขอบจริงอาจสูงกว่า 0.539) · ที่ 0.55 คำค้นสินค้าจริงยังเหลือของ >= 3 ชิ้น 39/40 คำ
#
# ⚠ **สิ่งที่ประตูนี้ทำไม่ได้ และไม่ได้ออกแบบให้ทำ**
# ที่ 0.55 ของในคลังผ่านประตูราว 78 จาก 100 ชิ้น → **ไม่ได้กรองของห่วยรายชิ้น**
# แยก "เสื่อโยคะ" (0.637) จาก "สายรัดเสื่อโยคะ" (0.607) ไม่ได้ เพราะทั้งคู่เป็นของในคลัง
# เรื่องนั้นเป็นงานของ **น้ำหนักความตรงในชั้นที่ 3** และทาง ข (เทียบคำหลัก) ถ้าทำ
#
# ⚠ คำค้นที่ "มีของใกล้เคียงแต่ไม่มีของตรงรุ่น" ประตูก็แยกไม่ได้ เช่น
# "claw hammer" (ค้อนหงอน) — คลังไม่มี แต่มีค้อนหนังที่ 0.567 จึงผ่านประตู
GATE = 0.55

# น้ำหนักชั้นที่ 3 — "ให้ความตรงโหวตหลายเสียง จนโหวตแพ้ไม่ได้ แต่ไม่ผูกขาด"
#
# ที่ต้องมี W_RELEVANCE เพราะถ้าชั้น 3 ไม่รู้เรื่องความตรงเลย (น้ำหนัก 0) จะเกิดกรณีนี้:
#   คำค้น "yoga mat" -> อันดับ 1 เป็น "Yoga Strap" $6.99, อันดับ 2 เป็น "Yoga Mat Bag"
#   เสื่อจริง $17.99 ตกไปอันดับ 3 เพราะแพงกว่าและรีวิวน้อยกว่า
# วัดแล้ว: 0 -> สายรัดชนะ · 1 -> เสื่อจริงขึ้นที่ 1 · 3 -> เสื่อจริง 2 ชิ้นใน 3 อันดับแรก
#
# ⚠ สูงเกินไปทำให้ไร้ประโยชน์ — ถ้าให้ 20 เสียง รีวิวกับความคุ้มถูกกลบหมด
#   ผลลัพธ์กลายเป็นเรียงตามความตรงเฉย ๆ = เท่ากับไม่ได้ rerank
#
# ⚠ ข้อจำกัดที่วัดแล้ว: น้ำหนัก 3 **ไม่พอ** สำหรับกรณีสุดขั้ว —
#   ของที่อยู่อันดับความตรงที่ 10 แต่เป็นที่ 1 ทั้งรีวิวและความคุ้ม ยังชนะ
#   ของที่อยู่อันดับความตรงที่ 1 แต่เป็นที่ 20 ทั้งคู่ (ต้องใช้ >= 3.70 จึงจะพลิก)
#   เก็บไว้ที่ 3 เพราะ (ก) แก้กรณีจริงที่วัดเจอได้แล้ว (เสื่อโยคะ vs สายรัดเสื่อ)
#   (ข) ในกองจริง อันดับความตรงที่ 1 กับ 10 ต่างกันแค่ ~0.004 (0.732 เทียบ 0.728)
#       การดันของที่ถูกและคุ้มกว่าขึ้นมาจึงเป็นพฤติกรรมที่ถูก ไม่ใช่ข้อบกพร่อง
#   (ค) ค่าจริงควรมาจาก 100 คู่ที่ติดป้าย ไม่ใช่จากกรณีสมมติที่แย่ที่สุด
#   ตัวที่กันของที่ไม่ตรงจริง ๆ คือ **ชั้นที่ 2 (ประตู)** ไม่ใช่น้ำหนักในชั้นนี้
W_RELEVANCE = 3
W_RATING = 1          # average_rating ดิบ
W_REVIEWS = 1         # rating_number — กันของ 5 ดาวรีวิวเดียวชนะของ 4.8 ดาวพันรีวิว
W_CATEGORY = 1        # หมวดของสินค้าตรงกับ catalog_category ในโปรไฟล์ผู้ใช้หรือไม่

# 🔑 **สัญญาณที่ 5 — คำซ้อนกัน** (เพิ่ม 2026-10-16 หลังตรวจสายพานทั้งเส้น)
# เหตุผล: ของดี (ป้าย >= 2) ตายที่ชั้นจัดอันดับ 48% มากกว่าทุกชั้นอื่นรวมกัน 8 เท่า
# และปรับน้ำหนัก 4 ตัวเดิมยังไงก็ไม่ขยับ (0.5846 -> 0.5847) เพราะ 4 ตัวนั้น
# **ไม่มีตัวไหนจับคำเงื่อนไขเฉพาะ** — เวกเตอร์ให้ป้าย 3 ได้ 0.639 ป้าย 0 ได้ 0.591
# แยกกันแทบไม่ออก ส่วนดาว/รีวิว/หมวด ไม่ได้วัดความตรงเลย
# การนับคำซ้อน **ผิดคนละแบบกับเวกเตอร์** จึงเสริมกันได้ (ป้าย 0 มัธยฐาน 0.333
# ป้าย >= 2 มัธยฐาน 0.667 จากป้ายคน 540 ชิ้น)
#
# น้ำหนัก 6 มาจากการกวาดค่าบนกองที่จำกัดเฉพาะของมีป้าย (eval/verify/rank_signals.py)
#   อังกฤษ 0.5535 -> 0.5990  **+4.5 จุด · ดีขึ้น 18 แย่ลง 4 · p = 0.0005**
#   ไทย    0.5955 -> 0.5869  -0.9 จุด · ดีขึ้น 6 แย่ลง 12 · p = 0.29
#                            (แยกจากความบังเอิญไม่ได้ แต่**ไม่ใช่ศูนย์** ต้องเขียนในเล่ม)
# ⚠ ที่ฝั่งไทยไม่ได้ประโยชน์ เพราะนับคำซ้อนกับ**คำแปล** ไม่ใช่คำของผู้ใช้
#   แปลเพี้ยนเมื่อไร สัญญาณนี้ก็เพี้ยนตาม — เป็นผลพวงของชั้นแปล ไม่ใช่ของชั้นนี้
# ⚠ ไม่เลือกค่าที่ดีที่สุด (คำซ้อนล้วนได้ +5.2) เพราะจะต้องถอด W_REVIEWS ซึ่งเป็น
#   ตัวกันของ 5 ดาวรีวิวเดียว และทำให้ฝั่งไทยเสียมากกว่า (-1.0 จุด)
W_WORDS = 6

# 🔑 **สัญญาณที่ 6 — ข้อกำหนดที่ขาดไม่ได้** (ขั้นที่ 2 · 2026-10-16)
# `W_WORDS` ให้น้ำหนักทุกคำในคำค้นเท่ากัน ทั้งที่บางคำชี้ขาดความตรง (2tb ·
# freestanding · gowdy) และบางคำเป็นเพียงชนิดสินค้า (drive · desk)
# ช่องนี้ให้ลูปส่ง**คำที่เป็นข้อกำหนดจริง** เข้ามาถ่วงหนักเป็นพิเศษ
# ว่างไว้ = สัญญาณเงียบ ผลเหมือนไม่มีช่องนี้เลย (ดู `order_by_votes`)
W_MUST = 12

# ⚠ ที่ต้องมี W_REVIEWS คู่กับ W_RATING เพราะเลิกใช้สูตรเบย์สแล้ว
# ดาวดิบอย่างเดียวทำให้ของ 5.0 ดาวรีวิวเดียวขึ้นอันดับ 1 ได้ (12.3% ของคลังเป็นแบบนั้น)
# การแยกเป็นสองสัญญาณให้ผลคล้ายการถ่วง แต่โปร่งใสกว่าและไม่ต้องตั้งค่า m เอง

# Reciprocal Rank Fusion — Cormack, Clarke & Büttcher (2009), SIGIR '09
# k = 60 คือค่าจากบทความต้นฉบับ · ใช้แค่ "อันดับ" ไม่ใช้ค่าดิบ จึงไม่ต้อง normalize
RRF_K = 60


# ---------------------------------------------------------------------------
# โครงสร้างข้อมูล
# ---------------------------------------------------------------------------

@dataclass
class Constraints:
    """เงื่อนไขที่ผู้ใช้ระบุชัด — ใช้ **ตัดทิ้ง** ไม่ใช่ลดคะแนน

    ของ $500 ตอนผู้ใช้บอกงบ $50 ไม่ควรโผล่มาเลย ไม่ว่าจะดีแค่ไหน
    (โปรเจกต์รุ่นก่อนก็ทำแบบนี้กับงบอยู่แล้ว — `agentic_rag.py` retrieve())

    ชื่อฟิลด์ตรงกับโปรไฟล์ 9 ช่องของ `memory.py` เพื่อให้ต่อกันได้ตรง ๆ
    (ทั้ง A1 และ A3 ส่งเข้ามาทางเดียวกันผ่าน `Profile.to_constraints()`)
    """
    budget_max: float | None = None
    budget_min: float | None = None
    category: str | None = None
    stores_excluded: list[str] = field(default_factory=list)
    titles_rejected: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any((self.budget_max, self.budget_min, self.category,
                        self.stores_excluded, self.titles_rejected))


@dataclass
class Ranked:
    """สินค้าหนึ่งชิ้นที่ผ่านประตูแล้ว พร้อม "ทำไมถึงได้อันดับนี้"

    เก็บอันดับของแต่ละสัญญาณไว้เพราะ:
      1. Generator ต้องเขียนเหตุผลให้ผู้ใช้อ่าน
      2. เขียนลงเล่มได้ว่าระบบตัดสินใจอย่างไร (สิ่งที่ cross-encoder ให้ไม่ได้)
    """
    hit: Hit
    score: float                 # คะแนนโหวตรวม
    rank_relevance: int
    rank_rating: int
    rank_reviews: int
    rank_category: int = 1
    rank_words: int = 1          # อันดับคำซ้อนกับคำค้น (สัญญาณที่ 5)
    rank_must: int = 1           # อันดับการตอบข้อกำหนดที่ขาดไม่ได้ (สัญญาณที่ 6)

    def why(self) -> str:
        return (f"ความตรง #{self.rank_relevance} · ดาว #{self.rank_rating} "
                f"· จำนวนรีวิว #{self.rank_reviews} · หมวด #{self.rank_category} "
                f"· คำซ้อน #{self.rank_words}")


@dataclass
class RerankResult:
    """ผลลัพธ์ทั้ง 3 อย่าง + ร่องรอยว่าแต่ละชั้นตัดไปเท่าไหร่"""
    picked: list[Hit]            # (1) ชิ้นที่เลือก -> Generator
    ranked: list[Ranked]         # (2) ทุกชิ้นที่ผ่าน เรียงแล้ว
    n_passed: int                # (3) ผ่านประตูกี่ชิ้น -> Planner

    n_candidates: int            # เข้ามากี่ชิ้น
    n_after_rules: int           # เหลือเท่าไหร่หลังชั้น 1
    n_skipped_duplicate: int     # ชั้น 4 ข้ามไปกี่ชิ้นเพราะร้านซ้ำ
    gate: float

    def enough(self, need: int = N_PICK) -> bool:
        """ของตรงพอจะตอบผู้ใช้หรือยัง — Planner ของ A3 ใช้ตัวนี้

        A4 ไม่เรียกตัวนี้ แต่ให้ LLM อ่าน `n_passed` แล้วตัดสินเอง
        (นี่คือจุดเดียวที่ A3 กับ A4 ต่างกัน)
        """
        return self.n_passed >= need

    def trace(self) -> dict:
        """สำหรับ trace dict ของ agent — เขียนลงเล่มและ debug ได้"""
        return {
            "n_candidates": self.n_candidates,
            "n_after_rules": self.n_after_rules,
            "n_passed": self.n_passed,
            "n_picked": len(self.picked),
            "n_skipped_duplicate": self.n_skipped_duplicate,
            "gate": self.gate,
            "weights": {"relevance": W_RELEVANCE, "rating": W_RATING,
                        "reviews": W_REVIEWS, "category": W_CATEGORY,
                        "words": W_WORDS},
            "picked": [{"id": r.hit.id, "title": r.hit.title, "why": r.why()}
                       for r in self.ranked[:len(self.picked)]],
        }


# ---------------------------------------------------------------------------
# ฟังก์ชันย่อย — แยกเป็นชั้น ๆ เพื่อทดสอบและเขียนลงเล่มได้ทีละชั้น
# ---------------------------------------------------------------------------

def _is_missing(v) -> bool:
    return v is None or v != v            # None หรือ NaN (NaN != NaN เป็นจริง)


# คำโครงสร้างที่ไม่ได้ชี้ว่าสินค้าตรงหรือไม่ตรง — ตัดทิ้งก่อนนับคำซ้อน
STOPWORDS = frozenset("the a an for with and of to in on set pack inch size".split())


def present(term: str, text: str) -> bool:
    """คำนี้อยู่ในข้อความไหม — ตัด s ท้ายคำออกด้วย เพราะ "dogs" อยู่ใน "Dog Toys"
    ไม่ได้ใช้ stemmer จริงเพราะต้องการให้ผลเดิมทุกครั้งและอธิบายได้ในเล่ม"""
    if term in text:
        return True
    return len(term) > 3 and term.endswith("s") and term[:-1] in text


def word_overlap(search_text: str, title: str) -> float:
    """สัดส่วนคำในคำค้นที่ปรากฏในชื่อสินค้า 0-1

    ตัดคำยาว <= 2 ตัวอักษรทิ้งด้วย เพราะ "a" "of" "2" จับคู่มั่วได้ง่าย
    **คำค้นว่าง -> คืน 0 ทุกชิ้น** สัญญาณจึงเงียบไปเอง (ทุกชิ้นได้อันดับเท่ากัน)
    ซึ่งทำให้ของเก่าที่ไม่ได้ส่ง search_text มา ได้ผลเหมือนเดิมเป๊ะ

        >>> word_overlap("claw hammer 16oz", "Claw Hammer 16oz Steel")
        1.0
        >>> word_overlap("claw hammer 16oz", "Screwdriver Set")
        0.0
    """
    q = {w for w in re.findall(r"[a-z0-9]+", search_text.lower())
         if w not in STOPWORDS and len(w) > 2}
    if not q:
        return 0.0
    tw = {w for w in re.findall(r"[a-z0-9]+", title.lower())
          if w not in STOPWORDS and len(w) > 2}
    return len(q & tw) / len(q)


def rank_descending(values: list) -> list[int]:
    """อันดับ (1 = ดีที่สุด) เมื่อ "ค่ามาก = ดี"

    - ค่าเท่ากันได้อันดับเดียวกัน (competition ranking: 1, 1, 3)
    - ค่าที่หาย (None/NaN) อยู่ **อันดับท้ายสุดร่วมกัน** = (จำนวนค่าที่มี) + 1
      ไม่ใช่ข้ามเทอมทิ้ง เพราะการข้ามทำให้เสียคะแนนมากกว่าช่วงอันดับทั้งหมด
      (k=60, N=30: 1/61 = 0.0164 เทียบกับช่วงอันดับทั้งหมด 1/61 - 1/90 = 0.0053)

    ยกมาจาก mark4/src/rerank.py — เหตุผลเชิงตัวเลขอยู่ในไฟล์นั้น
    """
    valid = [v for v in values if not _is_missing(v)]
    tail = len(valid) + 1
    return [tail if _is_missing(v) else 1 + sum(1 for x in valid if x > v)
            for v in values]


def apply_rules(hits: list[Hit], c: Constraints) -> list[Hit]:
    """ชั้น 1 — ตัดของที่ผิดเงื่อนไขที่ผู้ใช้บอกเอง

    **ตัดทิ้ง ไม่ใช่ลดคะแนน** เพราะเงื่อนไขพวกนี้ไม่มีการต่อรอง

    หลักฐานว่าชั้นนี้จำเป็น: คำค้น "wireless bluetooth earbuds" งบ $30
    3 อันดับแรกที่ค้นเจอตรงที่สุด แต่ราคา $49.95 / $38.88 / $39.88 เกินงบทั้งหมด
    ถ้าไม่มีชั้นนี้ ผู้ใช้จะได้ของที่ซื้อไม่ได้เป็น 3 อันดับแรก
    """
    if c.is_empty():
        return list(hits)

    rejected = {t.strip().lower() for t in c.titles_rejected if t}
    excluded = {s.strip().lower() for s in c.stores_excluded if s}
    out = []
    for h in hits:
        if c.budget_max is not None and (h.price is None or h.price > c.budget_max):
            continue
        if c.budget_min is not None and (h.price is None or h.price < c.budget_min):
            continue
        if excluded and h.store and h.store.strip().lower() in excluded:
            continue
        # ของที่ผู้ใช้ปฏิเสธแล้ว — เทียบแบบ "มีอยู่ในชื่อ" เพราะชื่อที่ Memory จำไว้
        # มักถูกตัดสั้นลงตอนแสดงผล จึงไม่ตรงกันทุกตัวอักษร
        if rejected:
            low = h.title.lower()
            if any(r in low or low in r for r in rejected):
                continue
        out.append(h)
    return out


def apply_gate(hits: list[Hit], gate: float = GATE) -> list[Hit]:
    """ชั้น 2 — ประตูความตรง: ต่ำกว่าเกณฑ์ = ตก

    **นี่คือชั้นที่สร้างเกณฑ์สัมบูรณ์** ที่ลูปของ A3/A4 ต้องใช้
    (ดูหมายเหตุเรื่องค่า GATE ด้านบน — ยังต้องวัดต่อ)
    """
    return [h for h in hits if h.score >= gate]


def order_by_votes(hits: list[Hit],
                   wanted_category: str | None = None,
                   w_relevance: int = W_RELEVANCE,
                   w_rating: int = W_RATING,
                   w_reviews: int = W_REVIEWS,
                   w_category: int = W_CATEGORY,
                   w_words: int = W_WORDS,
                   w_must: int = W_MUST,
                   search_text: str = "",
                   must_terms: list[str] | None = None,
                   k: int = RRF_K) -> list[Ranked]:
    """ชั้น 3 — เรียงแบบโหวต (RRF ถ่วงน้ำหนัก)

        คะแนน = w_ตรง/(k + อันดับความตรง)
               + w_รีวิว/(k + อันดับรีวิว)
               + w_คุ้ม/(k + อันดับความคุ้ม)

    ถ่วงน้ำหนักเพราะ RRF แบบน้ำหนักเท่ากันมีข้อบกพร่อง: ใน 3 สัญญาณมี 2 ตัว
    ที่ไม่ได้วัดความตรง จึงรวมหัวโหวตชนะความตรงได้ ตัวอย่างจริงด้วย k=60:
        A (ตรง #10, รีวิว #1,  คุ้ม #1 ) = 1/70 + 1/61 + 1/61 = 0.0471  ชนะ
        B (ตรง #1,  รีวิว #20, คุ้ม #20) = 1/61 + 1/80 + 1/80 = 0.0414
    สินค้าที่ตรงที่สุดแพ้ — ในงานค้นเอกสารไม่เป็นปัญหาเพราะทุกรายการวัดความตรง
    คนละวิธี แต่ของเรา 2 ใน 3 วัดคุณภาพสินค้า ไม่ได้วัดความตรง

    ⚠ น้ำหนัก 3 **ไม่ได้พลิกกรณีข้างบนนี้** (ต้อง >= 3.70) ดูเหตุผลที่เก็บไว้ที่ 3
    ในหมายเหตุของ W_RELEVANCE ด้านบน · RRF ใช้แค่อันดับ ไม่สนขนาดของความต่าง
    จึงไม่รู้ว่าอันดับ 10 แย่กว่าอันดับ 1 เยอะหรือนิดเดียว — ชั้นที่ 2 คือตัวกันเรื่องนั้น

    คะแนนเท่ากันเรียงตามอันดับความตรง (ให้ผลเดิมทุกครั้ง ไม่ขึ้นกับลำดับที่รับเข้ามา)
    """
    # ⚠ **อันดับความตรงใช้ `anchor_score` ถ้ามี** — คะแนนเทียบคำถามเดิมของผู้ใช้
    # ไม่ใช่เทียบคำค้นล่าสุดที่ลูปเขียนขึ้น · ประตูชั้น 2 ยังใช้ `score` ตามเดิม
    # เหตุผล: วัดแล้วถ้าเอา anchor_score ไปใช้ที่ประตูด้วย จะตัดของดีทิ้ง
    # (การทดลอง oracle: 57 เหลือ 37 คะแนน — docs/steps.md ข้อ 257-258)
    rel = rank_descending([h.anchor_score if h.anchor_score is not None else h.score
                           for h in hits])
    rat = rank_descending([h.rating for h in hits])
    rev = rank_descending([h.n_reviews for h in hits])

    # ตรงหมวด = 1 ไม่ตรง = 0 แล้วจัดอันดับด้วยตัวเดียวกับสัญญาณอื่น
    # ของที่ตรงได้อันดับ 1 ร่วม ที่เหลือได้อันดับถัดจากจำนวนที่ตรง
    # **ถ้าโปรไฟล์ยังไม่มีหมวด ทุกชิ้นได้ 0 เท่ากัน สัญญาณนี้จึงเงียบไปเอง**
    want = (wanted_category or "").strip()
    cat = rank_descending([1.0 if want and h.category == want else 0.0
                           for h in hits])

    # สัญญาณที่ 5 — คำซ้อนกับคำค้น · ถ้าไม่ส่ง search_text มา ทุกชิ้นได้ 0 เท่ากัน
    # อันดับจึงเท่ากันหมด กลายเป็นค่าคงที่บวกเท่ากันทุกชิ้น = ไม่มีผลต่อการเรียง
    wrd = rank_descending([word_overlap(search_text, h.title) for h in hits])

    # สัญญาณที่ 6 — ตอบข้อกำหนดที่ขาดไม่ได้กี่ข้อ · ไม่ส่งมา = ทุกชิ้นได้ 0 เท่ากัน
    must = must_terms or []
    mst = rank_descending([
        sum(1 for t in must if present(t, h.title.lower())) / len(must)
        if must else 0.0 for h in hits])

    ranked = [
        Ranked(hit=h,
               score=(w_relevance / (k + rel[i])
                      + w_rating / (k + rat[i])
                      + w_reviews / (k + rev[i])
                      + w_category / (k + cat[i])
                      + w_words / (k + wrd[i])
                      + w_must / (k + mst[i])),
               rank_relevance=rel[i], rank_rating=rat[i],
               rank_reviews=rev[i], rank_category=cat[i],
               rank_words=wrd[i], rank_must=mst[i])
        for i, h in enumerate(hits)
    ]
    ranked.sort(key=lambda r: (-r.score, r.rank_relevance, r.hit.id))
    return ranked


def pick_diverse(ranked: list[Ranked], n: int = N_PICK) -> tuple[list[Hit], int]:
    """ชั้น 4 — หยิบ n ชิ้น ห้ามร้านซ้ำ

    คืน (ชิ้นที่เลือก, จำนวนที่ข้ามเพราะร้านซ้ำ)

    หลักฐานว่าชั้นนี้จำเป็น: คำค้น "wireless bluetooth earbuds" งบ $30
    ถ้าไม่มีชั้นนี้ ร้าน CWNOTBHY จะได้ 2 ที่จาก 3 ที่ (อันดับ 2 และ 3)

    ถ้าของที่ไม่ซ้ำร้านไม่พอ n ชิ้น จะเติมของที่ร้านซ้ำกลับเข้าไป —
    เพราะคืน 2 ชิ้นดีกว่าคืน 2 ชิ้นแล้วบอกว่าไม่มีของ
    """
    picked, seen, skipped = [], set(), []
    for r in ranked:
        store = r.hit.store
        if store is not None and store in seen:
            skipped.append(r)
            continue
        picked.append(r.hit)
        if store is not None:
            seen.add(store)
        if len(picked) == n:
            return picked, len(skipped)

    # ไม่พอ -> เติมของที่ร้านซ้ำตามลำดับเดิม
    for r in skipped:
        if len(picked) == n:
            break
        picked.append(r.hit)
    return picked, len(skipped)


# ---------------------------------------------------------------------------
# หน้าตาเดียวที่สถาปัตยกรรมเรียกใช้
# ---------------------------------------------------------------------------

def rerank(hits: list[Hit],
           constraints: Constraints | None = None,
           n_pick: int = N_PICK,
           gate: float = GATE,
           search_text: str = "",
           w_words: int | None = None,
           must_terms: list[str] | None = None,
           w_must: int | None = None) -> RerankResult:
    """คัด 4 ชั้นแล้วคืนผลลัพธ์ 3 อย่าง

        >>> with Retriever() as r:
        ...     hits = r.search("wireless bluetooth earbuds", k=100)
        >>> res = rerank(hits, Constraints(budget_max=30))
        >>> res.n_passed          # Planner ใช้ตัวนี้ตัดสินว่าจะค้นซ้ำไหม
        73
        >>> [h.title for h in res.picked]
        ['Wireless Earbuds Bluetooth 5.3 ...', ...]
    """
    c = constraints or Constraints()
    after_rules = apply_rules(hits, c)
    passed = apply_gate(after_rules, gate)
    # `w_words` เปิดให้ผู้เรียก**เปลี่ยนน้ำหนักคำซ้อนตอนรันได้** — ลูปของ A3/A3C
    # ใช้ช่องนี้จัดอันดับกองเดิมใหม่เมื่อเห็นว่าชื่อสินค้าไม่มีคำที่ผู้ใช้ขอ
    ranked = order_by_votes(passed, wanted_category=c.category,
                            search_text=search_text,
                            w_words=W_WORDS if w_words is None else w_words,
                            must_terms=must_terms,
                            w_must=W_MUST if w_must is None else w_must)
    picked, n_skipped = pick_diverse(ranked, n_pick)

    return RerankResult(
        picked=picked,
        ranked=ranked,
        n_passed=len(passed),
        n_candidates=len(hits),
        n_after_rules=len(after_rules),
        n_skipped_duplicate=n_skipped,
        gate=gate,
    )
