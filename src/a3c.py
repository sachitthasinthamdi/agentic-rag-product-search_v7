"""แขน A3C — **Agentic RAG ที่ agent คุมแค่การเลือก action** ลูปเป็นกฎโค้ด

**ต่างจาก A3 แค่ฟังก์ชันเดียว** — `_decide_loop()` · ที่เหลือสืบทอดมาทั้งหมด
(ความจำ · Planner · ชั้นแปล · ค้น · Reranker · ลูปค้น · Generator เหมือนกันเป๊ะ)

```
A3C:  โค้ด  ถาม "ผ่านประตู >= 3 ไหม และค้นไม่เกิน 3 ครั้งไหม"
A3:   LLM   ถาม "ของที่ได้พอจะแนะนำ 3 ชิ้นแล้วหรือยัง"
```

**นี่คือตัวแปรเดียวที่เปลี่ยน** ทำให้คู่ A3C ↔ A3 เป็นการเปลี่ยนตัวแปรทีละตัวจริง

## ทำไมต้องมีแขนนี้

⚠ **แก้คำกล่าวอ้างเมื่อขั้นที่ 202** — เดิมเขียนว่าแขนนี้เป็น "Iterative RAG
ไม่ใช่ Agentic RAG" โดยยึดเกณฑ์เดียวคือใครคุมลูป **ซึ่งแคบเกินไปและไม่ตรง**
เพราะแขนนี้สืบทอด `respond()` จาก A3 จึง**มี Planner ที่ LLM คุมด้วย** และ
Planner ที่เลือกระหว่าง `ask` / `chat` / `search` ตอนรัน คือ **single-agent
router** ซึ่ง Singh et al. 2025 นับเป็น Agentic RAG รูปแบบที่ง่ายที่สุด

หลักฐานว่า router ทำงานจริง ไม่ใช่แค่ในนิยาม — ในการวัด 140 คำค้น Planner
เบี่ยงไม่ส่งไปค้น **1/140 ทั้งสองภาษา** ส่วน A1 ที่ไม่มี Planner ได้ **0/140**

| แขน | ชั้นเลือก action (router) | ชั้นคุมลูป | จัดเป็น |
|---|---|---|---|
| A1 | ไม่มี | ไม่มี | **RAG มาตรฐาน** (Advanced RAG) |
| **A3C** | **LLM** | **โค้ด** | **Agentic RAG · agent คุมแค่การเลือก action** |
| A3 | **LLM** | **LLM** | **Agentic RAG · agent คุมทั้ง action และลูป** |

(Gao et al. 2024 arXiv 2407.21059 — iterative/recursive/adaptive retrieval อยู่ใน
อนุกรมวิธาน RAG · Singh et al. 2025 arXiv 2501.09136 — single-agent router)

ถ้าไม่มีแขนนี้ เล่มจะตอบไม่ได้ว่า**ควรให้ agent ตัดสินใจกว้างแค่ไหน**
ซึ่งเป็นคำถามที่โปรเจกต์นี้มีหลักฐานรองรับอยู่แล้ว

## ⚠ หลักฐานที่ทำนายว่าแขนนี้จะชนะ A3 (ขั้น 5.6)

| ใครตัดสินว่าจะวน | ความแม่น | Cohen κ |
|---|---|---|
| **โค้ด (แขนนี้)** | **91.7%** | **0.824** |
| LLM พรอมต์ที่ดีที่สุด (A3) | — | 0.676 |
| LLM พรอมต์แรก | — | 0.000 |

การตัดสินว่า "ของพอหรือยัง" เป็น**เรื่องตัวเลข** ซึ่งขั้น 5.6 วัดไว้ว่าโค้ดแม่นกว่า
ส่วนการ**เขียนคำค้นใหม่**เป็นเรื่องภาษา ซึ่ง LLM ชนะ (κ 0.646 เทียบ 0.280)
→ แขนนี้จึงยังใช้ LLM เขียนคำค้น เหมือน A3 ทุกประการ **เปลี่ยนแค่คนตัดสิน**

## ประหยัดกว่า A3

ไม่ต้องเรียก LLM ถามว่าจะวนไหม → **ประหยัด 1 ครั้งต่อรอบลูป**

รัน:  python src\\a3c.py                      (โหมดคุยต่อเนื่อง)
      python src\\a3c.py "ค้อนหงอน"            (ถามครั้งเดียว — ดูการวนจริง)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a3 import A3, SearchRound, _show, should_search_again         # noqa: E402
from rerank import RerankResult                                   # noqa: E402


class A3C(A3):
    """Agentic RAG ที่ agent คุมแค่การเลือก action — ลูปเป็นกฎโค้ด

        >>> with A3C() as arm:
        ...     turn = arm.respond("ค้อนหงอน")
        ...     print(turn.trace["loop_by_llm"])
        0
    """

    name = "A3C"
    description = ("Agentic RAG · agent คุมแค่การเลือก action — "
                   "โค้ดตัดสินว่าจะวน · LLM เขียนคำค้นใหม่")

    def _decide_loop(self, result: RerankResult, searches: int,
                     rounds: list[SearchRound]) -> tuple[bool, str, int]:
        """**โค้ดตัดสิน — ฟังก์ชันเดียวที่ต่างจาก A3** จึงใช้ LLM 0 ครั้ง

        บันทึก `by_llm=False` ทุกรอบ เพื่อให้ `loop_by_llm` ของแขนนี้เป็น 0 เสมอ
        → ตรวจย้อนได้ว่าแขนนี้ไม่มี LLM อยู่ในการตัดสินเลย
        """
        again, why = should_search_again(result, searches, self.n_pick,
                                         self.max_searches)
        self._loop_log.append({"round": searches, "by_llm": False,
                               "search_again": again,
                               "n_passed": result.n_passed})
        return again, why, 0


# ---------------------------------------------------------------------------
def main() -> None:
    args = sys.argv[1:]
    with A3C() as arm:
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
