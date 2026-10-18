"""แขน A1 — **RAG มาตรฐาน** ตามโครง 5 ขั้นที่กำหนดไว้

```
คำถาม ──▶ Memory ──▶ ชั้นแปล + Retriever ──▶ Reranker ──▶ Generator ──▶ ตอบ
          (ขั้น 2)        (ขั้น 3)            (ขั้น 4)      (ขั้น 5)
```

## โครง 5 ขั้นที่กำหนด แมปกับโค้ดตรงไหน

| ขั้นในโครง | ทำอะไร | โมดูล |
|---|---|---|
| 1 User Query | รับข้อความ | `respond()` |
| 2 Understand User Context | ดึงความต้องการ งบประมาณ ความชอบจากบทสนทนา | `memory.py` |
| 3 Retrieve Relevant Products | ค้นจากฐานสินค้า 81,264 ชิ้น | `translate.py` + `retrieval.py` |
| 4 Recommendation & Ranking | จัดอันดับตามความต้องการด้วย scoring algorithm | `rerank.py` |
| 5 LLM Generates Explanation | อธิบายโดยอ้างข้อมูลสินค้าที่ค้นพบ | `generate.py` |

## สิ่งที่แขนนี้ไม่มี — และตั้งใจไม่ให้มี

| | |
|---|---|
| **Planner** | ❌ **ค้นทุกครั้งเสมอ** ไม่เลือกว่าจะค้น จะถามกลับ หรือจะคุย |
| **ลูปค้นซ้ำ** | ❌ ค้นครั้งเดียวจบ ไม่ว่าของที่ได้จะแย่แค่ไหน |

**สองอย่างนี้คือทั้งหมดที่ A3 มีเพิ่ม** — ชั้นควบคุมอิสระที่ตัดสินใจเองว่าจะทำอะไรต่อ
จึงทำให้คู่ **A1 ↔ A3** แยกผลของ *ความเป็น agentic* ออกมาได้ตรง ๆ
โดยที่ทั้งสองฝ่ายมีความจำ การค้น และการจัดอันดับเหมือนกันหมด

**เรียก LLM 2 ครั้ง** (Memory · Generator) · +1 ถ้าคำถามเป็นภาษาไทย (ชั้นแปล)

⚠ **ใช้ `translate.search()` ไม่ใช่ `Retriever.search()` ตรง ๆ** — ทุกแขนต้องใช้
ตัวเดียวกัน ไม่งั้นแขนที่ลืมแปลจะเสียเปรียบและผลเทียบไม่แฟร์

รัน:  python src\\a1.py                        (โหมดคุยโต้ตอบ)
      python src\\a1.py "เสื่อโยคะกันลื่น"      (ถามครั้งเดียว)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memory                                                    # noqa: E402
import translate                                                 # noqa: E402
from generate import Answer, generate                            # noqa: E402
from memory import Profile                                       # noqa: E402
from rerank import RerankResult, rerank                          # noqa: E402
from retrieval import Hit, Retriever                             # noqa: E402

# ผู้เข้าชิงที่ดึงมาให้ Reranker — **ต้องเท่ากับ A3** ไม่งั้น Reranker คนละฐานกัน
N_CANDIDATES = 100
# ส่งให้ Generator กี่ชิ้น — **ต้องเท่ากับ A3** ไม่งั้นทับซ้อน@3 คิดจากคนละฐาน
N_PICK = 3


@dataclass
class Turn:
    """ผลของหนึ่งรอบสนทนา — โครงเดียวกับ A3 เพื่อให้วัดเทียบกันได้"""
    question: str
    reply: str
    hits: list[Hit] = field(default_factory=list)
    trace: dict = field(default_factory=dict)


class A1:
    """RAG มาตรฐาน — จำบริบท ค้น จัดอันดับ แล้วอธิบาย

        >>> with A1() as arm:
        ...     turn = arm.respond("เสื่อโยคะกันลื่น งบไม่เกิน 30")
        ...     print(turn.trace["rerank"]["n_passed"])
    """

    name = "A1"
    description = "RAG มาตรฐาน — ความจำ + ค้น + จัดอันดับ + อธิบาย · ไม่มี Planner ไม่มีลูป"

    def __init__(self, n_candidates: int = N_CANDIDATES, n_pick: int = N_PICK):
        self.n_candidates = n_candidates
        self.n_pick = n_pick
        self.profile = Profile()
        self.history: list[dict] = []
        self._retriever = Retriever()

    def __enter__(self) -> A1:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        self._retriever.close()

    def reset(self) -> None:
        """เริ่มบทสนทนาใหม่ — ล้างความจำ (ใช้ตอนวัดผลให้แต่ละคำถามเป็นเอกเทศ)"""
        self.profile = Profile()
        self.history = []

    def respond(self, message: str) -> Turn:
        message = (message or "").strip()
        if not message:
            return Turn(question=message, reply="กรุณาพิมพ์ข้อความครับ",
                        trace={"arm": self.name, "skipped": "ข้อความว่าง",
                               "llm_calls": 0, "embed_calls": 0})

        # ภาษาของคำตอบ — ตรวจด้วยการนับอักษรไทย ไม่เรียก LLM
        language = translate.detect_language(message)

        # ---- ขั้น 2 Understand User Context ----
        update = memory.update(self.profile, message, self.history)
        self.profile = update.profile
        llm_calls = update.llm_calls

        # ---- ขั้น 3 Retrieve — ค้นด้วยโปรไฟล์ที่สะสมไว้ ----
        # ไม่มี Planner คั่น จึง **ค้นทุกครั้งเสมอ** แม้คำถามจะคลุมเครือ
        query = memory.profile_to_query(self.profile, message)
        hits, plan = translate.search(self._retriever, query, k=self.n_candidates)
        llm_calls += int(plan.used_llm)

        # ---- ขั้น 4 Recommendation & Ranking ----
        # ส่ง `plan.search_text` (คำค้นอังกฤษที่ใช้ค้นจริง) ให้สัญญาณคำซ้อนใช้ได้
        result: RerankResult = rerank(hits, self.profile.to_constraints(),
                                      n_pick=self.n_pick,
                                      search_text=plan.search_text)

        # ---- ขั้น 5 LLM Generates Explanation ----
        # ใช้สัญญาณ weak เหมือน A3 เพราะ Generator ต้องเหมือนกันทุกแขน
        weak = result.n_passed < self.n_pick
        answer: Answer = generate(message, result.picked, language, weak=weak)

        self._remember(message, answer.reply)
        return Turn(
            question=message,
            reply=answer.reply,
            hits=result.picked,
            trace={
                "arm": self.name,
                "language": language,
                "memory": update.trace(),
                "query": {"built": query, **plan.trace()},
                "n_hits": len(hits),
                "top_score": round(hits[0].score, 4) if hits else None,
                "rerank": result.trace(),
                "generator": answer.trace(),
                "llm_calls": llm_calls + answer.llm_calls,
                "embed_calls": 1,
                "n_searches": 1,
                # ⚠ A1 เดินหน้าต่อแม้ผ่านประตู 0 ชิ้น — A3 จะใช้ค่านี้ตัดสินใจค้นใหม่
                # เก็บไว้เพื่อ**รายงานได้ว่าลูปของ A3 จะยิงกี่เปอร์เซ็นต์ของคำถาม**
                "would_loop": not result.enough(self.n_pick),
            },
        )

    def _remember(self, user_message: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": reply})


# ---------------------------------------------------------------------------
# รันเองเพื่อดูผล
# ---------------------------------------------------------------------------

def _show(turn: Turn) -> None:
    t = turn.trace
    print(f"\n{'=' * 74}")
    print(f"ถาม: {turn.question}   [{t.get('arm')} · {t.get('language')}]")

    if "memory" in t:
        m = t["memory"]
        changed = m.get("changed") or []
        print(f"ความจำ: {'เพิ่ม ' + ', '.join(changed) if changed else 'ไม่มีอะไรใหม่'}")

    if "query" in t:
        q = t["query"]
        arrow = f"  ->  {q['search_text']}" if q["language"] == "th" else ""
        print(f"คำค้น:  {q['built']}{arrow}")

    if "rerank" in t:
        r = t["rerank"]
        print(f"คัด:    ค้นมา {t['n_hits']} ชิ้น · ผ่านประตู {r.get('n_passed')} ชิ้น "
              f"· เลือก {len(turn.hits)} ชิ้น")

    print(f"{'-' * 74}")
    print(turn.reply)
    print(f"{'-' * 74}")
    if turn.hits:
        for h in turn.hits:
            price = f"${h.price:,.2f}" if h.price is not None else "-"
            print(f"  [{h.score:.3f}] {price:>9}  {h.title[:52]}")
    bad = t.get("generator", {}).get("unsupported_numbers") or []
    if bad:
        print(f"⚠ ตัวเลขในคำตอบที่ไม่พบในข้อมูลที่ส่งไป: {bad}")
    print(f"เรียก LLM {t.get('llm_calls', 0)} ครั้ง · embedding {t.get('embed_calls', 0)} ครั้ง"
          f" · A3 จะค้นใหม่ไหม {'ใช่' if t.get('would_loop') else 'ไม่'}")


def main() -> None:
    args = sys.argv[1:]
    with A1() as arm:
        if args:
            _show(arm.respond(" ".join(args)))
            return
        print(f"{arm.name} — {arm.description}")
        print("พิมพ์คำถาม (เว้นว่างแล้วกด Enter เพื่อออก)")
        while True:
            try:
                question = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question:
                break
            _show(arm.respond(question))


if __name__ == "__main__":
    main()
