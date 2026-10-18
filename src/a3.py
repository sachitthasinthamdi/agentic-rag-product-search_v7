"""แขน A3 — **Agentic RAG** ลูปค้นซ้ำที่ **LLM** ตัดสินว่าจะวนไหม

```
            Memory
               │  โปรไฟล์ 9 ช่อง + บันทึกคำค้นที่ลองไปแล้ว
               ▼
            Planner ─────▶ ถามกลับ / คุยทั่วไป
               │
               ▼  recommend
        ┌──────────────────────────────┐
        │  ชั้นแปล + ค้น ──▶ Reranker   │
        │        ▲              │      │
        │        └──────────────┘      │   ◀── วนตรงนี้ LLM ตัดสิน
        │      ยังไม่พอ ขยายคำค้น       │
        └──────────────┬───────────────┘
                       ▼ พอแล้ว หรือหมดทาง
                   Generator ──▶ ตอบ
```

**ความต่างจาก RAG มาตรฐาน (A1) มีสามอย่าง**

  1. **Planner** เลือกเองว่าจะค้น ถามกลับ หรือคุยทั่วไป
  2. ถ้าของตรงไม่พอ → **LLM ตัดสินว่าจะค้นใหม่ไหม** แล้ว **LLM เขียนคำค้นใหม่**
  3. Memory บันทึกคำค้นที่ลองไปแล้ว ไม่ให้ค้นซ้ำคำเดิม

## 🔑 ทำไมต้องให้ LLM ตัดสินว่าจะวน (เปลี่ยนเมื่อขั้น 141)

การมีลูปไม่ได้ทำให้เป็น agentic — **สิ่งที่ทำให้เป็น agentic คือชั้นที่ LLM
ตัดสินใจเองตอนรัน** และระบบนี้มี **2 ชั้นแบบนั้น** คือ Planner (เลือก action)
กับการคุมลูป · แขนนี้ให้ LLM คุม**ทั้งสองชั้น**

| ชั้นที่ LLM ตัดสินใจเองได้ | A1 | A3C | A3 |
|---|---|---|---|
| Planner เลือก `ask` / `chat` / `search` | ✗ | **✓** | **✓** |
| คุมลูป — จะค้นซ้ำไหม | ✗ | ✗ (กฎโค้ด) | **✓** |

อ้างอิง Gao et al. 2024 arXiv 2407.21059 (Modular RAG — iterative/recursive/adaptive
retrieval อยู่ในอนุกรมวิธาน RAG อยู่แล้ว) · Singh et al. 2025 arXiv 2501.09136
(single-agent router คือ Agentic RAG รูปแบบที่ง่ายที่สุด)

⚠ **แก้คำกล่าวอ้างเมื่อขั้นที่ 202** — เดิมเขียนว่า "เดิมโค้ดตัดสิน ซึ่งคือ
Iterative RAG ไม่ใช่ Agentic RAG" ซึ่ง**ไม่ตรง** เพราะยึดเกณฑ์เดียวคือใครคุมลูป
แล้วละเลยว่า A3C มี Planner อยู่ด้วย · **A3C เป็น Agentic RAG เหมือนกัน**
ต่างกันแค่**ขอบเขตที่ agent ตัดสินใจ** ดังนั้นคู่ A3C ↔ A3 ตอบคำถามว่า
**ควรขยายขอบเขตการตัดสินใจของ agent ไปถึงการคุมลูปด้วยไหม**

⚠ **ผลที่คาดไว้ตามหลักฐานที่วัดเอง — แขนนี้อาจแย่ลง**

ขั้น 5.6 วัดกับคำตอบที่คนติดป้ายไว้ว่า

| ใครตัดสินว่าจะวน | ความแม่น | Cohen κ |
|---|---|---|
| **โค้ด** (กฎ `ผ่านประตู < 3`) | **91.7%** | **0.824** |
| LLM พรอมต์ที่ดีที่สุด | — | 0.676 |
| LLM พรอมต์แรก | — | 0.000 |

**ถ้า A3 แย่ลงจริง นั่นคือผลการทดลอง ไม่ใช่ความผิดพลาด** — เป็นหลักฐานว่าการย้าย
การตัดสินเชิงตัวเลขไปให้โมเดล 8B ทำให้คุณภาพตก ซึ่งเป็นข้อค้นพบที่เล่มรายงานได้

เพดานจำนวนรอบ (`MAX_SEARCHES`) **ยังเป็นของโค้ด** เพราะเป็นเรื่องความปลอดภัย
ไม่ใช่การตัดสินคุณภาพ · ถ้าให้ LLM คุมด้วย ระบบอาจวนไม่จบ

⚠ **A3 ไม่ใช่ "ทำซ้ำได้ 100%"** เพราะมี LLM ทั้งตัดสินและเขียนคำค้นอยู่ในลูป

รัน:  python src\\a3.py                     (โหมดคุยต่อเนื่อง)
      python src\\a3.py "ค้อนหงอน"           (ถามครั้งเดียว — ดูการวนจริง)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memory                                                    # noqa: E402
import planner                                                   # noqa: E402
import numpy as np
import rewrite                                                   # noqa: E402
from critique import missing_terms                               # noqa: E402
import translate                                                 # noqa: E402
from generate import Answer, generate, generate_chat, generate_question  # noqa: E402
from memory import Profile                                       # noqa: E402
from rerank import RerankResult, rerank                          # noqa: E402
from retrieval import Hit, Retriever                             # noqa: E402

N_CANDIDATES = 100
N_PICK = 3
MAX_SEARCHES = 3             # ค้นได้ไม่เกินกี่ครั้งต่อหนึ่งคำถาม — กันวนไม่จบ
# ⚠⚠ **ปิดไว้ — ทดลองแล้วไม่ผ่าน** (17 ต.ค. 2026)
#
# (ข้อ 6) บังคับค้นซ้ำเมื่อของครบแล้วแต่ชื่อสินค้าไม่มีคำที่ผู้ใช้ขอถึงสัดส่วนนี้
# ใส่เข้าไปเพราะลูปเดิมยิงเฉพาะตอน "ของไม่พอ" จึงไม่เคยทำงานใน 80/140 คำค้น
#
# **แต่วัด end-to-end แล้วเป็นที่มาของการแพ้ทั้งหมด**
#
#   เหตุที่ลูปยิง              อังกฤษ        ไทย
#   ของไม่พอ (ผ่านประตู < 3)   ชนะ 7 แพ้ 0   ชนะ 5 แพ้ 0   ← 12-0 ไม่เคยพลาด
#   กฎคำซ้อน (ข้อนี้)          ชนะ 2 แพ้ 3   ชนะ 3 แพ้ 1   ← เสมอตัว
#
# ถอดออกแล้วจำลองได้ **อังกฤษ ดีขึ้น 8 แย่ลง 0 (p = 0.0078)** · **ไทย 7-0 (p = 0.0156)**
# คือ agentic ไม่แพ้ RAG แม้แต่ข้อเดียว
#
# **สาเหตุที่คิดผิด** เข้าใจว่า "ชื่อสินค้าไม่มีคำที่ผู้ใช้ขอ = ของไม่ตรง"
# แต่ความจริงคือ**คลังใช้คำเรียกต่างจากผู้ใช้** กระถางที่ปลูกกุหลาบได้ไม่จำเป็น
# ต้องมีคำว่า rose ในชื่อ → กฎนี้ปลุกลูปในข้อที่ระบบทำถูกอยู่แล้ว
# ตรงกับที่ Adaptive-RAG (arXiv 2403.14403) เตือนว่าการค้นวนในคำค้นที่ไม่ต้องวน
# ทำให้ผลแย่ลง
#
# 🔑 **สัญชาตญาณเดียวกันใช้ได้ที่ชั้นจัดอันดับ แต่ใช้ไม่ได้ที่สวิตช์เปิดลูป** —
# `W_WORDS` ใน rerank.py คือตัวนับคำซ้อนเหมือนกันและ**ได้ผลดี +3.4 ถึง +3.5 จุด**
# เพราะจัดอันดับคือการเปรียบเทียบของในกองเดียวกัน ส่วนเปิดลูปต้องใช้เกณฑ์สัมบูรณ์
# ซึ่งคำซ้อนไม่ใช่เกณฑ์สัมบูรณ์ที่ดี
#
# เปิดกลับด้วย USE_WORD_MATCH_LOOP = True · docs/steps.md ข้อ 334 เป็นต้นไป
USE_WORD_MATCH_LOOP = False
WORD_MATCH = 0.34            # เกณฑ์ที่ใช้ตอนทดลอง
                             # = 'ได้ของครบแต่น่าจะไม่ตรง' -> ค้นเพิ่มอีกรอบ
                             # วัดกับป้าย 540 ชิ้น: ป้าย 0 มัธยฐาน 0.333 · ป้าย>=2 0.667
                             # แยกได้ดีกว่าคะแนนเวกเตอร์มาก (ซึ่งต่างกันแค่ 0.048)
STOPWORDS = frozenset("the a an for with and of to in on set pack inch size".split())
TYPE_GUARD = 0.65            # (ขั้น 2) คำค้นที่เขียนใหม่ต้องใกล้คำถามเดิมอย่างน้อยเท่านี้
# ⚠⚠ **ปิดไว้ — ทดลองแล้วไม่ผ่าน อย่าเปิดโดยไม่อ่านก่อน** (16 ต.ค. 2026)
#
# (ขั้น 2 ข) ให้ agent บอกว่าข้อกำหนดข้อไหนที่ผลลัพธ์ยังไม่ตอบ แล้วจัดอันดับใหม่
# วัดแบบ end-to-end ฝั่งอังกฤษ 140 คำค้น × 3 แขนแล้ว **ทำให้แย่ลง**
#
#   ก่อนเปิด ข  กลุ่มคลังมีของ  A3C = A1 เป๊ะทุกทศนิยม (0.5594)
#   เปิด ข      กลุ่มคลังมีของ  A3C 0.5866 เทียบ A1 0.5995  **-1.3 จุด**
#               กลุ่มมีงบจำกัด  A3C 0.5189 เทียบ A1 0.5497  **-3.1 จุด**
#   กลุ่มคลังไม่มีของ ไม่กระทบ เพราะ `picked` ว่าง โค้ดข้าม action นี้ไปเอง
#
# สาเหตุ: โมเดล 8B เลือก "คำไหนเป็นข้อกำหนด" ไม่แม่น ทิ้งคำที่ควรเก็บ (`gowdy`
# = แบรนด์) และเก็บคำที่ไม่ใช่ข้อกำหนด → ถ่วงผิดคำ ของดีหลุดจาก 3 อันดับแรก
# ซ้ำรอยกับ κ 0.08-0.25 ของ LLM-as-judge ที่ mark5 วัดไว้
#
# **เก็บโค้ดไว้ไม่ลบ** เพราะตัวเลขข้างบนต้องทำซ้ำได้เพื่ออ้างในเล่ม
# เปิดกลับด้วย USE_CRITIQUE = True · รายละเอียดใน docs/steps.md ข้อ 292-313
USE_CRITIQUE = False
W_MUST_LOOP = 6              # น้ำหนักที่ใช้ตอนทดลอง (ค่าที่เสียน้อยสุดจาก 6/12/24)
                             # วัดจากคำค้นจริง 148 คู่ในการรัน: คำที่เพี้ยนอยู่ <= 0.552
                             # (peacock->crane 0.420 · rudin->rude man 0.499)
                             # คำที่ดีเริ่มที่ 0.705 (loui vuitton->louis vuitton handbag 0.739
                             # peacock->peafowl 0.754) — 0.65 คือกลางช่องว่างที่ไม่มีข้อมูลเลย


@dataclass
class SearchRound:
    """ร่องรอยของการค้นหนึ่งครั้ง — ไว้เขียนลงเล่มว่าลูปทำอะไรไปบ้าง"""
    round: int
    broaden: int
    query: str
    search_text: str
    n_hits: int
    n_passed: int
    top_score: float | None
    n_pool: int = 0          # (ขั้น 1) ขนาดกองสะสมหลังรวมรอบนี้

    def summary(self) -> str:
        return (f"รอบ {self.round} (ขยายชั้น {self.broaden}) {self.query!r} "
                f"-> ผ่านประตู {self.n_passed}/{self.n_hits}")


@dataclass
class Turn:
    question: str
    reply: str
    hits: list[Hit] = field(default_factory=list)
    trace: dict = field(default_factory=dict)


def word_match(search_text: str, titles: list[str]) -> float:
    """สัดส่วนคำในคำค้นที่ปรากฏในชื่อสินค้า — มัธยฐานของสินค้าที่หยิบมา

    **ทำไมต้องมีสัญญาณนี้** เวกเตอร์จับความใกล้เชิงหัวข้อได้ แต่พลาดคำเงื่อนไข
    เฉพาะเจาะจง (freestanding · 9 feet · 1TB) ซึ่งเป็นคำที่ชี้ขาดว่าตรงหรือไม่ตรง
    การนับคำซ้อนจึงเป็นสัญญาณที่**ผิดคนละแบบกับเวกเตอร์** จึงเสริมกันได้

    วัดกับป้ายจากคน 540 ชิ้น — ป้าย 0 มัธยฐาน 0.333 · ป้าย >= 2 มัธยฐาน 0.667
    เทียบกับคะแนนเวกเตอร์ที่ต่างกันแค่ 0.591 กับ 0.639 (แยกไม่ออก)

        >>> word_match("claw hammer", ["Claw Hammer 16oz", "Screwdriver Set"])
        0.5
    """
    q = {w for w in re.findall(r"[a-z0-9]+", search_text.lower())
         if w not in STOPWORDS and len(w) > 2}
    if not q or not titles:
        return 1.0                       # วัดไม่ได้ -> ถือว่าผ่าน ไม่ไปรบกวนลูปเดิม
    shares = []
    for t in titles:
        tw = {w for w in re.findall(r"[a-z0-9]+", t.lower())
              if w not in STOPWORDS and len(w) > 2}
        shares.append(len(q & tw) / len(q))
    shares.sort()
    mid = len(shares) // 2
    return shares[mid] if len(shares) % 2 else (shares[mid - 1] + shares[mid]) / 2


def should_search_again(result: RerankResult, searches: int, need: int,
                        max_searches: int = MAX_SEARCHES) -> tuple[bool, str]:
    """**กฎการวนแบบโค้ดล้วน — ตอนนี้เป็นทางสำรอง ไม่ใช่ทางหลัก**

    ⚠ ตั้งแต่ขั้น 141 A3 ให้ **LLM** ตัดสินว่าจะวนไหม (ดูหัวไฟล์ว่าทำไม)
    ฟังก์ชันนี้เก็บไว้ 2 เหตุผล
      1. เป็น**เส้นเทียบของเล่ม** — กฎนี้แม่น 91.7% (κ = 0.824) ที่วัดไว้ในขั้น 5.6
      2. ใช้เมื่อ LLM ตอบผิดรูป (`planner.decide_loop()` เรียกกฎเดียวกันนี้เอง)

    คืน (วนไหม, เหตุผล) — เหตุผลถูกเก็บลง trace เพื่ออธิบายได้ว่าทำไมหยุด

        >>> should_search_again(RerankResult([], [], 0, 0, 0, 0, 0.55), 1, 3)[0]
        True
    """
    if result.n_passed >= need:
        return False, f"ของตรงพอแล้ว ({result.n_passed} ชิ้น)"
    if searches >= max_searches:
        return False, f"ค้นครบ {max_searches} ครั้งแล้ว ยอมตอบด้วยของที่มี"
    return True, f"ของตรงแค่ {result.n_passed} ชิ้น ยังไม่ถึง {need}"


class A3:
    """Agentic RAG — ค้นซ้ำได้ โดย **LLM** ตัดสินว่าจะวนไหม

        >>> with A3() as arm:
        ...     turn = arm.respond("ค้อนหงอน")
        ...     print(turn.trace["n_searches"])
    """

    name = "A3"
    description = ("Agentic RAG · agent คุมทั้ง action และลูป — "
                   "LLM ตัดสินว่าจะวน · LLM เขียนคำค้นใหม่ · โค้ดคุมแค่เพดานรอบ")

    def __init__(self, n_candidates: int = N_CANDIDATES, n_pick: int = N_PICK,
                 max_searches: int = MAX_SEARCHES):
        self.n_candidates = n_candidates
        self.n_pick = n_pick
        self.max_searches = max_searches
        self.profile = Profile()
        self.history: list[dict] = []
        self.ask_count = 0
        self._retriever = Retriever()
        # บันทึกว่าแต่ละรอบ "LLM ตัดสิน" หรือ "ตกไปใช้กฎโค้ด" -> เล่มต้องรายงานสัดส่วนนี้
        self._loop_log: list[dict] = []

    def __enter__(self) -> A3:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        self._retriever.close()

    def reset(self) -> None:
        self.profile = Profile()
        self.history = []
        self.ask_count = 0

    # -- 🔑 จุดที่ทำให้ลูปนี้เป็น Agentic RAG -------------------------------
    def _decide_loop(self, result: RerankResult, searches: int,
                     rounds: list[SearchRound]) -> tuple[bool, str, int]:
        """**LLM ตัดสินว่าจะค้นใหม่ไหม** · คืน (วนไหม, เหตุผล, จำนวน LLM ที่ใช้)

        โค้ดเหลือหน้าที่เดียวคือ**เพดานจำนวนรอบ** ซึ่งเป็นเรื่องความปลอดภัย
        ไม่ใช่การตัดสินคุณภาพ — ถ้าให้ LLM คุมด้วย ระบบอาจวนไม่จบ

        `planner.decide_loop()` **ไม่บอกเกณฑ์ตัวเลขในพรอมต์** ไม่งั้นก็เท่ากับ
        เอากฎของโค้ดไปให้ LLM อ่าน แล้วการวัดจะไม่มีความหมาย
        """
        if searches >= self.max_searches:
            self._loop_log.append({"round": searches, "by_llm": False,
                                   "reason": "เพดานรอบ"})
            return False, f"โค้ด: ค้นครบ {self.max_searches} ครั้งแล้ว", 0

        decision = planner.decide_loop(result.n_passed, searches,
                                       self.profile.tried_queries)
        self._loop_log.append({"round": searches, "by_llm": decision.by_llm,
                               "search_again": decision.search_again,
                               "n_passed": result.n_passed})
        return decision.search_again, decision.reason, decision.llm_calls

    # ---------------------------------------------------------------------
    def respond(self, message: str) -> Turn:
        message = (message or "").strip()
        if not message:
            return Turn(question=message, reply="กรุณาพิมพ์ข้อความครับ",
                        trace={"skipped": "ข้อความว่าง", "llm_calls": 0})

        language = translate.detect_language(message)

        update = memory.update(self.profile, message, self.history)
        self.profile = update.profile
        decision = planner.decide(self.profile, message, self.ask_count)

        trace: dict = {"arm": self.name, "language": language,
                       "memory": update.trace(), "planner": decision.trace()}
        llm_calls = update.llm_calls + decision.llm_calls

        if decision.action in ("ask", "chat"):
            if decision.action == "ask":
                answer = generate_question(self.profile.to_dict(), message, language)
                self.ask_count += 1
            else:
                answer = generate_chat(message, language)
            trace.update({"generator": answer.trace(), "n_searches": 0, "n_hits": 0,
                          "llm_calls": llm_calls + answer.llm_calls, "embed_calls": 0})
            self._remember(message, answer.reply)
            return Turn(question=message, reply=answer.reply, trace=trace)

        # ================= ลูปค้นซ้ำ =================
        self._loop_log = []
        rounds: list[SearchRound] = []
        searches = 0
        hits: list[Hit] = []
        result: RerankResult | None = None
        stop_reason = "ไม่ได้ค้นเลย"

        # รอบแรกค้นด้วยโปรไฟล์ที่สะสมไว้ (ผ่านชั้นแปลถ้าเป็นไทย)
        query: str | None = memory.profile_to_query(self.profile, message)
        rewritten = False
        # (ข) เวกเตอร์ของ**คำถามเดิม** — ใช้เป็นหลักให้คะแนนทุกรอบ
        # เดิมรอบที่ 2 ขึ้นไปให้คะแนนเทียบคำค้นที่เขียนใหม่ ประตูคัดจึงกว้างตามคำค้น
        anchor_vector: list[float] | None = None
        # (ขั้น 1) กองผู้เข้าชิงสะสมข้ามรอบ — เดิมใช้เฉพาะผลรอบสุดท้าย ของรอบก่อนถูกทิ้ง
        # ทำได้เพราะ (ข) ทำให้ทุกรอบให้คะแนนเทียบคำถามเดิมเหมือนกัน คะแนนจึงเทียบกันได้
        pool: dict[str, Hit] = {}
        anchor_text = ""            # (ข้อ 6) คำค้นอังกฤษรอบแรก ใช้วัดคำซ้อน
        reranked_by: list[str] = []  # (ขั้น 2 ข) คำที่ทำให้ลูปจัดอันดับใหม่
        forced = 0                  # จำนวนรอบที่ลูปยิงเพราะ 'ของครบแต่คำไม่ตรง'

        while query is not None:
            self.profile.tried_queries.append(query)
            if rewritten:
                # คำค้นที่ LLM เขียนใหม่เป็นภาษาอังกฤษแล้ว ไม่ต้องแปลอีก
                hits = self._retriever.search(query, k=self.n_candidates)
                search_text = query
                # (ข ฉบับแก้) เติมคะแนนเทียบคำถามเดิมไว้ใน anchor_score
                # **ไม่ทับ score** เพราะ score คือสิ่งที่ประตูชั้น 2 ใช้
                # เดิมทับทิ้งทำให้ประตูตัดของดีที่คำค้นใหม่หาเจอ (oracle 57 -> 37)
                if anchor_vector is not None and hits:
                    anchor = self._retriever.score_against(
                        [h.id for h in hits], anchor_vector)
                    for h in hits:
                        h.anchor_score = anchor.get(h.id, 0.0)
            else:
                hits, plan = translate.search(self._retriever, query,
                                              k=self.n_candidates)
                llm_calls += int(plan.used_llm)
                search_text = plan.search_text
                # (ข) รอบแรกคือคำถามเดิม เก็บเวกเตอร์ไว้เป็นหลักของทุกรอบถัดไป
                if anchor_vector is None:
                    anchor_vector = self._retriever.embed_query(search_text)
                    anchor_text = search_text
                # รอบแรกคะแนนคือเทียบคำถามเดิมอยู่แล้ว คัดลอกไว้ให้ทั้งกองเทียบกันได้
                for h in hits:
                    h.anchor_score = h.score
            searches += 1

            for h in hits:                      # (ขั้น 1) สะสม ตัดซ้ำด้วย id
                keep = pool.get(h.id)
                if keep is None or h.score > keep.score:
                    pool[h.id] = h
            # ⚠ ใช้ `anchor_text` = คำค้นอังกฤษ**รอบแรก** ไม่ใช่คำที่ลูปเขียนใหม่
            # ด้วยเหตุผลเดียวกับ anchor_score: กองสะสมข้ามรอบ ถ้าวัดคำซ้อนกับ
            # คำค้นล่าสุด ของจากรอบก่อนจะถูกตัดสินด้วยคำที่ไม่ได้ใช้ค้นมัน
            result = rerank(list(pool.values()), self.profile.to_constraints(),
                            n_pick=self.n_pick, search_text=anchor_text)
            rounds.append(SearchRound(
                round=searches, broaden=int(rewritten), query=query,
                search_text=search_text, n_hits=len(hits),
                n_passed=result.n_passed, n_pool=len(pool),
                top_score=round(hits[0].score, 4) if hits else None))

            again, stop_reason, used = self._decide_loop(result, searches, rounds)
            llm_calls += used

            # (ข้อ 6) ได้ของครบแล้วแต่ชื่อสินค้าไม่มีคำที่ผู้ใช้ขอ = น่าจะไม่ตรง ค้นเพิ่ม
            # เดิมลูปยิงเฉพาะตอน "ของไม่พอ" จึงไม่เคยทำงานในกลุ่มที่คลังมีของ (80/140 คำ)
            # ปลอดภัยเพราะขั้น 1 สะสมกองไว้ — รอบเพิ่มทำได้แค่เติม ไม่ทำให้ของเดิมหาย
            # 🔑 (ขั้น 2 ข) **action ที่ A1 ทำไม่ได้** — เห็นผลแล้วค่อยลงมือ
            # agent บอกว่าข้อกำหนดข้อไหนที่ 3 ชิ้นนี้ยังไม่ตอบ แล้วโค้ดจัดอันดับ
            # **กองเดิม** ใหม่โดยถ่วงคำนั้นหนักขึ้น — ไม่ค้นซ้ำ ไม่เพิ่มรอบ
            # ทำครั้งเดียวต่อคำถาม (รอบแรก) เพราะเป็นการวินิจฉัยคำถาม ไม่ใช่ของกอง
            if USE_CRITIQUE and searches == 1 and result.picked:
                must = missing_terms(anchor_text,
                                     [h.title for h in result.picked])
                llm_calls += 1
                if must:
                    result = rerank(list(pool.values()),
                                    self.profile.to_constraints(),
                                    n_pick=self.n_pick, search_text=anchor_text,
                                    must_terms=must, w_must=W_MUST_LOOP)
                    reranked_by = must

            wm = word_match(anchor_text, [h.title for h in result.picked])
            if (USE_WORD_MATCH_LOOP and not again and wm < WORD_MATCH
                    and searches < self.max_searches):
                again = True
                forced += 1
                stop_reason = (f"ของครบแต่ชื่อสินค้ามีคำที่ผู้ใช้ขอแค่ {wm:.0%} "
                               f"(เกณฑ์ {WORD_MATCH:.0%}) — ค้นเพิ่ม")
            if not again:
                break

            # ให้ LLM คิดคำค้นใหม่ · คืน None = คิดไม่ออก -> หยุดแล้วตอบว่าไม่พบ
            query = rewrite.rewrite(message, self.profile.tried_queries)
            llm_calls += 1
            rewritten = True
            # (ขั้น 2) โค้ดตรวจว่าคำค้นใหม่ยังเป็นสินค้าชนิดเดิมไหม — LLM เขียน โค้ดตรวจ
            # ตรงกับหลักของโปรเจกต์: κ บอกว่าโค้ดชนะเรื่องกฎ 0.824 ต่อ 0.000
            if query is not None and anchor_vector is not None:
                qv = np.asarray(self._retriever.embed_query(query), dtype=np.float32)
                av = np.asarray(anchor_vector, dtype=np.float32)
                denom = float(np.linalg.norm(qv) * np.linalg.norm(av))
                sim = float(qv @ av) / denom if denom else 0.0
                if sim < TYPE_GUARD:
                    drifted, query = query, None
                    stop_reason = (f"คำค้นใหม่ '{drifted}' หลุดจากสิ่งที่ผู้ใช้ขอ "
                                   f"(ใกล้เคียง {sim:.2f} < {TYPE_GUARD}) — ตอบว่าไม่พบดีกว่า")
            if query is None:
                stop_reason = "คิดคำค้นใหม่ไม่ได้แล้ว — ตอบว่าไม่พบดีกว่าตอบของที่ไม่ตรง"
        # ============================================

        picked = result.picked if result else []
        # ของตรงไม่ถึงจำนวนที่ต้องการ -> บอก Generator ให้ไม่ยืนยันว่าตรง
        # (เดิมเหตุผลที่หยุดเขียนว่า "ตอบว่าไม่พบดีกว่า" แต่โค้ดยังเอาของไม่ตรงไปตอบ
        #  ซึ่งขัดกันเอง — ตอนนี้ตอบได้แต่ต้องมีคำเตือนกำกับ)
        weak = bool(result) and result.n_passed < self.n_pick
        answer: Answer = generate(message, picked, language, weak=weak)

        self.ask_count = 0
        self._remember(message, answer.reply)
        trace.update({
            "n_searches": searches,
            "forced_by_word_match": forced,
            "reranked_by": reranked_by,
            "word_match": round(word_match(anchor_text,
                                           [h.title for h in picked]), 3),
            "rounds": [r.__dict__ for r in rounds],
            "stop_reason": stop_reason,
            # ใครตัดสินแต่ละรอบ -> เล่มรายงานได้ว่า LLM ตอบผิดรูปกี่ %
            "loop_decisions": list(self._loop_log),
            "loop_by_llm": sum(1 for d in self._loop_log if d["by_llm"]),
            "loop_by_code": sum(1 for d in self._loop_log if not d["by_llm"]),
            "n_hits": len(hits),
            "rerank": result.trace() if result else None,
            "generator": answer.trace(),
            "llm_calls": llm_calls + answer.llm_calls,
            "embed_calls": searches,
            "tried_queries": list(self.profile.tried_queries),
        })
        return Turn(question=message, reply=answer.reply, hits=picked, trace=trace)

    def _remember(self, user_message: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": reply})


# ---------------------------------------------------------------------------
def _show(turn: Turn) -> None:
    t = turn.trace
    print(f"\n{'=' * 74}")
    print(f"ถาม: {turn.question}   [{t.get('arm', '?')}]")
    if "memory" in t:
        prof = {k: v for k, v in t["memory"]["profile"].items()
                if v not in ("", None, [])}
        print(f"ความจำ: {prof or 'ยังว่าง'}")
    if "planner" in t:
        p = t["planner"]
        print(f"แผน:    {p['action']}  ({'LLM' if p['by_llm'] else 'โค้ด'})")
    for r in t.get("rounds", []):
        print(f"  ค้นรอบ {r["round"]} ({"LLM เขียนใหม่" if r["broaden"] else "จากโปรไฟล์"}) {r['query']!r}"
              f"  ->  ผ่านประตู {r['n_passed']}/{r['n_hits']}"
              f"  (สูงสุด {r['top_score']})")
    if t.get("stop_reason"):
        print(f"หยุดเพราะ: {t['stop_reason']}")
    print(f"{'-' * 74}")
    print(turn.reply)
    if turn.hits:
        print(f"{'-' * 74}")
        for h in turn.hits:
            price = f"${h.price:,.2f}" if h.price is not None else "-"
            print(f"  [{h.score:.3f}] {price:>9}  {h.title[:52]}")
    print(f"ค้น {t.get('n_searches', 0)} ครั้ง · เรียก LLM {t.get('llm_calls', 0)} ครั้ง "
          f"· embedding {t.get('embed_calls', 0)} ครั้ง")


def main() -> None:
    args = sys.argv[1:]
    with A3() as arm:
        if args:
            _show(arm.respond(" ".join(args)))
            return
        print(f"{arm.name} — {arm.description}")
        print("คุยต่อเนื่องได้ · พิมพ์ reset เพื่อล้างความจำ · Enter ว่างเพื่อออก")
        while True:
            try:
                message = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not message:
                break
            if message == "reset":
                arm.reset()
                print("ล้างความจำแล้ว")
                continue
            _show(arm.respond(message))


if __name__ == "__main__":
    main()
