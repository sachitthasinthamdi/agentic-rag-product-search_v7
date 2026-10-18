"""โมดูล Planner — ตัดสินว่ารอบนี้จะทำอะไร

**mark7 มีแค่ A3 ที่ใช้ไฟล์นี้** — A1 ไม่มี Planner จึงค้นทันทีทุกครั้ง
และนั่นคือ 1 ใน 2 ชั้นที่ทำให้ A3 เป็น agentic ส่วน A1 ไม่เป็น
และเป็น **จุดที่ A2/A3/A4 ต่างกัน** ตาม `docs/architecture.md`

| แขน | Planner ถูกเรียก | ตัวเลือก |
|---|---|---|
| A2 | **1 ครั้งต่อรอบ** | `ask` `chat` `recommend` |
| A3/A4 | **ทุกรอบของลูป** | `ask` `chat` `search` `answer` |

ไฟล์นี้ทำของ A2 ก่อน (`decide()`) และเปิดช่องให้ A3/A4 เพิ่ม `decide_loop()` ทีหลัง

⚠ **มีทางสำรองที่เป็นโค้ดเสมอ** — หลักฐานจากขั้น 5.2 บอกว่าโมเดลขนาด 8B
ไม่ทำตามกฎในพรอมต์ของตัวเอง (เมินตัวอย่างที่ตรงทุกตัวอักษร · ละเมิดกฎที่เขียนไว้ ·
ให้ผลเหมือนกันทั้งที่เปลี่ยนโครงสร้างพรอมต์) → **ห้ามเชื่อผลจาก LLM โดยไม่ตรวจ**
ถ้า LLM ตอบ action ที่ไม่มีอยู่ โค้ดจะตัดสินให้จากความครบของโปรไฟล์

⚠ ต้องสตาร์ต Ollama ก่อน:  ollama.exe serve
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory import Profile, _chat_json                           # noqa: E402
from translate import CHAT_MODEL                                 # noqa: E402

ACTIONS = ("ask", "chat", "recommend")
MAX_ASKS = 2                 # ถามกลับได้ไม่เกินกี่ครั้งต่อหนึ่งความต้องการ

PLAN_SYSTEM = """คุณคือ Planner เลือกการกระทำของรอบนี้จากสามตัวเลือก

- "recommend": รู้หมวดสินค้าหรือการใช้งานอย่างน้อยหนึ่งอย่างแล้ว หรือผู้ใช้ขอให้แนะนำ
- "ask": ยังไม่รู้เลยว่าผู้ใช้อยากได้สินค้าประเภทไหน เช่น "อยากได้ของสักอย่าง"
- "chat": ทักทาย คุยเล่น หรือถามข้อมูลทั่วไป ไม่ได้ขอสินค้า

หลักคิด: อย่าถามพร่ำเพรื่อ ถ้ารู้หมวดสินค้าแล้วให้ recommend ทันที

ตอบ JSON: {"action": "...", "reason": "เหตุผลสั้น ๆ"}"""


@dataclass
class Decision:
    action: str
    reason: str
    by_llm: bool             # LLM ตัดสิน หรือโค้ดตัดสินแทน
    llm_calls: int = 0

    def trace(self) -> dict:
        return {"action": self.action, "reason": self.reason,
                "by_llm": self.by_llm, "llm_calls": self.llm_calls}


def fallback(profile: Profile, ask_count: int) -> Decision:
    """ตัดสินด้วยโค้ดล้วน — ใช้เมื่อ LLM ตอบไม่ได้เรื่อง

    ทำซ้ำได้ 100% และเป็นตัวที่ทำให้ A2 ไม่ล้มเมื่อโมเดลเพี้ยน
    """
    if profile.is_empty() and ask_count < MAX_ASKS:
        return Decision("ask", "โค้ดตัดสิน: ยังไม่รู้ว่าผู้ใช้อยากได้อะไร", by_llm=False)
    return Decision("recommend", "โค้ดตัดสิน: รู้ความต้องการพอแล้ว", by_llm=False)


def decide(profile: Profile, user_message: str, ask_count: int = 0,
           model: str = CHAT_MODEL) -> Decision:
    """เลือก action ของรอบนี้ (A2)

        >>> decide(Profile(category="หูฟัง"), "มีอะไรแนะนำ").action
        'recommend'

    ลำดับการตัดสิน
      1. ถาม LLM
      2. ถ้า LLM ตอบ action ที่ไม่มีอยู่ -> ใช้ `fallback()`
      3. **กันการถามพร่ำเพรื่อ** — ถ้าเลือก `ask` แต่รู้หมวดแล้ว หรือถามไปครบโควตา
         โค้ดจะเปลี่ยนเป็น `recommend` ทับ (ผู้ใช้จริงเลิกคุยถ้าถูกถามวนไปวนมา)
    """
    user = (f"โปรไฟล์: {json.dumps(profile.to_dict(), ensure_ascii=False)}\n"
            f'ข้อความล่าสุด: "{user_message}"\n'
            f"ถามกลับไปแล้ว {ask_count} ครั้ง\nเลือก action")

    result = _chat_json(PLAN_SYSTEM, user, model)
    action = str(result.get("action", "")).strip().lower()

    if action not in ACTIONS:
        decision = fallback(profile, ask_count)
        decision.llm_calls = 1
        decision.reason = f"LLM ตอบ {result.get('action', 'ว่าง')!r} ซึ่งไม่มีอยู่ → {decision.reason}"
        return decision

    reason = str(result.get("reason", "")).strip() or "ไม่ได้ให้เหตุผล"

    if action == "ask" and (profile.category or ask_count >= MAX_ASKS):
        why = "รู้หมวดสินค้าแล้ว" if profile.category else f"ถามครบ {MAX_ASKS} ครั้งแล้ว"
        return Decision("recommend", f"โค้ดเปลี่ยนจาก ask: {why}",
                        by_llm=False, llm_calls=1)

    return Decision(action, reason, by_llm=True, llm_calls=1)


# ---------------------------------------------------------------------------
# การตัดสินใจวนลูป — ใช้โดย A4 เท่านั้น (A3 ใช้กฎในโค้ดที่ `a3.py`)
#
# ⚠ **พรอมต์นี้เลือกมาจากการวัด 4 แบบในขั้น 5.6** ไม่ใช่เขียนลอย ๆ
#
#   พรอมต์                        ความแม่น   Cohen κ
#   "เลือก action: search/answer"   41.7%    0.000   <- ตอบ search ทุกข้อ ใช้ไม่ได้
#   สลับลำดับตัวเลือก               41.7%    0.000
#   บอกว่าการค้นซ้ำมีต้นทุน          50.0%    0.122
#   **"ของพอจะแนะนำ 3 ชิ้นไหม"**    83.3%    0.676   <- ที่ใช้
#   (กฎในโค้ดของ A3)               91.7%    0.824
#
# **ถ้าใช้พรอมต์แบบเลือก action จะเป็นการจัดฉากให้ A4 แพ้** เพราะมันจะวนจนครบ
# เพดานทุกครั้งโดยไม่เคยตัดสินใจเลย → ผลเทียบ A3 vs A4 จะไม่ยุติธรรม
#
# สิ่งที่เปลี่ยนคือ **ถามให้ตรงกับงานที่โมเดลทำได้** — ถามเป็นคำถามตัดสินว่า
# "พอหรือยัง" (ตอบ true/false) ไม่ใช่ให้เลือกชื่อการกระทำ
#
# ⚠ คาดการณ์ไว้แล้วว่า **A4 จะไม่ดีกว่า A3** (0.676 เทียบ 0.824)
# ซึ่งเป็นคำตอบของคำถามวิจัย ไม่ใช่ความล้มเหลว — ดู `docs/architecture.md`
ENOUGH_SYSTEM = """ระบบแนะนำสินค้าต้องแนะนำสินค้า 3 ชิ้นให้ผู้ใช้
ดูจำนวนสินค้าที่ผ่านเกณฑ์ความตรง แล้วตอบว่าพอจะแนะนำ 3 ชิ้นได้หรือยัง

ตอบ JSON: {"enough": true หรือ false, "reason": "เหตุผลสั้น ๆ"}"""


@dataclass
class LoopDecision:
    search_again: bool
    reason: str
    by_llm: bool
    llm_calls: int = 0


def decide_loop(n_passed: int, searches: int, tried: list[str],
                model: str = CHAT_MODEL) -> LoopDecision:
    """ให้ LLM ตัดสินว่าของที่ได้พอจะตอบหรือยัง (A4)

    **ไม่ได้บอกเกณฑ์ตัวเลขในพรอมต์** เพราะถ้าบอกก็เท่ากับเอากฎของ A3 ไปให้ LLM อ่าน
    → A4 จะกลายเป็น A3 และการเทียบจะไม่มีความหมาย

    ถ้า LLM ตอบไม่เป็น true/false → ใช้กฎในโค้ดแทน และบันทึกว่าโค้ดตัดสิน
    (ขั้น 5.2 และ 5.5 แสดงว่าโมเดลขนาดนี้ตอบผิดรูปได้ ต้องมีทางสำรองเสมอ)
    """
    user = (f"จำนวนสินค้าที่ผ่านเกณฑ์ความตรง: {n_passed} ชิ้น\n"
            f"ค้นมาแล้ว: {searches} ครั้ง\n"
            f"คำค้นที่ลองไปแล้ว: {', '.join(tried)}\n"
            f"พอจะแนะนำ 3 ชิ้นได้หรือยัง")

    result = _chat_json(ENOUGH_SYSTEM, user, model)
    value = result.get("enough")

    if not isinstance(value, bool):
        again = n_passed < 3
        return LoopDecision(again, f"LLM ตอบ {value!r} ไม่ใช่ true/false "
                                   f"→ โค้ดตัดสิน: ผ่านประตู {n_passed} ชิ้น",
                            by_llm=False, llm_calls=1)

    reason = str(result.get("reason", "")).strip() or "ไม่ได้ให้เหตุผล"
    return LoopDecision(search_again=not value,
                        reason=f"LLM ว่า{'พอแล้ว' if value else 'ยังไม่พอ'}: {reason}",
                        by_llm=True, llm_calls=1)
