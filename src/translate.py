"""ขั้นที่ 5.2 — ชั้นแปลภาษา ไทย → อังกฤษ ก่อนค้น

**ทำไมต้องมี:** ข้อมูลสินค้าเป็นภาษาอังกฤษ 100% (ชื่อสินค้าที่มีอักษรไทย 0 แถว)
แต่ระบบต้องรับคำถามภาษาไทย · ขั้นที่ 4.4 วัดแล้วพบว่าค้นด้วยไทยตรง ๆ ได้ผล
ทับซ้อนกับฝั่งอังกฤษแค่ **25.3%** และคะแนนฝั่งไทยต่ำกว่าทุกคำถามราว 0.08
มีกรณีผิดชัด ๆ เช่น "เสื้อยืดผ้าฝ้ายสีดำ" ได้เสื้อกล้าม · "กระเป๋าสะพายข้างหนังผู้หญิง"
ได้กระเป๋าสะพายไหล่

**ดัชนีไม่ต้องสร้างใหม่** — แก้ที่ฝั่งคำค้นอย่างเดียว

**2 เรื่องที่ออกแบบไว้เพื่อไม่ให้ชั้นนี้กลายเป็นตัวแปรปนในการทดลอง:**

  1. `temperature = 0` → ถามซ้ำได้คำตอบเดิม
  2. **จำคำแปลไว้ (cache)** → คำค้นเดิมในลูปรอบที่ 2 ไม่เรียก LLM ซ้ำ

เหตุผลเดียวกับที่ Reranker ไม่ใช้ LLM: วิทยานิพนธ์ต้องวัดว่า "ลูปช่วยไหม"
ถ้าชั้นแปลให้คำตอบไม่เหมือนกันทุกครั้ง จะแยกไม่ออกว่าผลที่เปลี่ยนมาจากลูปหรือจากชั้นแปล

**คำถามภาษาอังกฤษไม่เรียก LLM เลย** — ตรวจภาษาด้วยช่วงรหัสอักขระ ซึ่งแน่นอน 100%
และไม่มีต้นทุน → ประหยัด 1 ครั้งต่อรอบสำหรับคำถามอังกฤษ

⚠ ต้องสตาร์ต Ollama ก่อน:  ollama.exe serve
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed import OLLAMA_URL                                     # noqa: E402

# โมเดลภาษาไทย — ตัวเดียวกับที่ A2 ใน agentic-rag-demo ใช้
CHAT_MODEL = "scb10x/llama3.1-typhoon2-8b-instruct"
TIMEOUT = 120
MAX_CHARS = 200              # คำค้นที่ยาวกว่านี้แปลว่าไม่ใช่คำค้นสินค้า

# ช่วงรหัสอักขระไทยใน Unicode
THAI_START, THAI_END = 0x0E00, 0x0E7F

TRANSLATE_SYSTEM = """แปลคำค้นหาสินค้าจากภาษาไทยเป็นภาษาอังกฤษ ตามหลัก 5 ข้อ

ใช้คำที่ร้านค้าใช้ ไม่แปลตรงตัว    เครื่องเย็บกระดาษ -> stapler
ห้ามเปลี่ยนชนิดสินค้า             พัดลมตั้งพื้น -> pedestal fan
คงตัวเลขและหน่วยไว้               ปลั๊กพ่วง 3 เมตร -> 3 meter extension cord
คงคำขยายของผู้ใช้ไว้ครบ           ขวดน้ำเก็บความเย็น -> insulated water bottle
ห้ามเติมคำที่ผู้ใช้ไม่ได้พูด         ที่วางโน้ตบุ๊ก -> laptop stand

ตอบเฉพาะคำค้นภาษาอังกฤษบรรทัดเดียว ห้ามอธิบาย ห้ามใส่เครื่องหมายคำพูด"""

# ================= การตัดสินใจเรื่องพรอมต์ (3 ต.ค. 2026) =================
#
# แบบที่ใช้: **สอนหลักการ 5 ข้อ บรรทัดละข้อ** (478 ตัวอักษร)
# ผู้ใช้เลือกแบบสอนหลักการเพราะตัวอย่างในพรอมต์ไม่ทับกับคำค้นที่ใช้วัดผลชุดใดเลย
# แล้วสั่งให้ย่อให้สั้นลง → รุ่นนี้ย่อจาก 881 เหลือ 478 ตัวอักษร (21 เหลือ 9 บรรทัด)
#
#   ทับซ้อน@5 กับคำค้นอังกฤษที่คนเขียน (เพดานบน = 100%)
#
#   พรอมต์                      ทดสอบ1(25)  ทดสอบ2(15)  รวม(40)   ความยาว
#   ไทยล้วน ไม่แปล                 28.0%      17.3%     24.0%      -
#   แบบให้ตัวอย่าง (ไม่ใช้)         70.4%      84.0%     75.5%    ~430
#   แบบหลักการ ยาว                 67.2%      66.7%     67.0%     881
#   **แบบหลักการ สั้น  <- ที่ใช้**  69.6%      72.0%     70.5%     478
#   แบบหลักการ สั้นสุด (รวมกฎ)      65.6%      76.0%     69.5%     323
#
# **เหตุผลที่ย่อแล้วใช้รุ่นนี้: สั้นลงเกือบครึ่งโดยคะแนนไม่ตก** ไม่ใช่เพราะคะแนนดีขึ้น
# (ส่วนต่าง 3.5 จุดอยู่ในช่วงความคลาดเคลื่อน ดูหมายเหตุเรื่องความเสถียรด้านล่าง)
# รุ่นยาวและแบบให้ตัวอย่างเก็บไว้วัดซ้ำได้ใน tools/compare_prompts.py
#
# ⚠⚠ **ความเสถียร: temperature=0 ไม่ได้ให้คำตอบเดิม 100%**
# วัดจริง: ถามซ้ำ 3 รอบด้วยพรอมต์เดียวกัน เหมือนกัน **14/15 คำค้น**
#   "เสื้อเชิ้ตแขนยาวผู้ชาย" รอบ 1 ได้ men's long-sleeve shirt (ถูก)
#                            รอบ 2-3 ได้ men's long-sleeve dress shirt (ผิด)
# → คำค้นเดียวที่พลิกทำให้คะแนนบนชุด 15 คู่ขยับ 6.7 จุด
# → **ส่วนต่างต่ำกว่า ~7 จุดบนชุดเล็กเชื่อไม่ได้ ต้องวัดซ้ำหลายรอบ**
# → cache ด้านล่างช่วยให้ภายในบทสนทนาเดียวนิ่ง แต่ข้ามรอบการรันไม่รับประกัน
#
# **ข้อสังเกตที่พบตอนวัด:** โมเดลละเมิดกฎที่เขียนไว้ในพรอมต์ของตัวเอง เช่น
# "ที่นอนยางพารา -> rubber mattress" (ผิดข้อ 1 ที่ห้ามแปลตรงตัว · ที่ถูกคือ latex) และ
# "เสื้อเชิ้ตแขนยาวผู้ชาย -> ... dress shirt" (ผิดข้อ 5 ที่ห้ามเติมคำ)
# → **เขียนกฎลงพรอมต์ไม่ได้ทำให้โมเดลทำตามกฎ** มีผลต่อการออกแบบ Planner ของ A4
#
# ถ้าจะปรับพรอมต์นี้ต่อ ให้ปรับบน DEV_PAIRS เท่านั้น แล้ววัดด้วยชุดที่ยังไม่เคยใช้
# ========================================================================

# ⚠ ตัวอย่างทั้ง 5 ข้อข้างบนเป็น **ภาพประกอบของหลักการ** ไม่ใช่เฉลยของคำค้นที่จะวัด
#
# สินค้าในตัวอย่าง (stapler · backpack · extension cord · water bottle · laptop stand)
# **ไม่มีอันไหนอยู่ใน eval/queries.py TEST_PAIRS** เพราะพรอมต์รุ่นก่อนเอาคำค้น 3 คู่
# จากชุดวัดผลมาเขียนเป็นตัวอย่างแล้ววัดด้วยชุดนั้นเอง (test-set contamination)
#
# ข้อ 2 เป็นรุ่นที่ 2 — รุ่นแรกเขียนว่า "เลือกชื่อประเภทที่แคบที่สุด" แล้ววัดได้ 52%
# (พรอมต์เดิมได้ 75% ในกลุ่มเดียวกัน) เพราะ "แคบที่สุด" ไม่มีจุดหยุด โมเดลจึงแคบเลย
# ไปถึงชิ้นส่วนย่อย เช่น ขอเครื่องวัดความดันแล้วได้ผ้าพันแขน และบางครั้งขัดกับข้อ 4
# (ทิ้งคำขยายของผู้ใช้ไป) · รุ่นนี้เปลี่ยนเป็น "ห้ามเปลี่ยนชนิดสินค้าหลัก" ซึ่งมีจุดหยุดชัด
# ตัวอย่างสองบรรทัดกันคนละทิศ: pedestal fan กันการแคบผิดทิศ · backpack กันการกว้างเกิน
#
# ที่เลือกสอน "สะพายหลัง -> backpack" แทน "สะพายข้าง -> crossbody" เป็นของจงใจ:
# ชุดทดสอบมีคำค้น "สะพายข้าง" อยู่ → ถ้าโมเดลตอบ crossbody ได้เอง แปลว่ามันเข้าใจ
# **หลักการ** ข้อ 2 และขยายไปใช้กับคำที่ไม่เคยสอนได้ · ถ้ายังตอบ shoulder แปลว่า
# มันทำได้แค่ลอกตัวอย่าง — ทั้งสองผลลัพธ์เป็นข้อค้นพบที่เขียนลงเล่มได้

# จำคำแปลไว้ทั้งโปรเซส — คำค้นเดิมไม่เรียก LLM ซ้ำ
_CACHE: dict[str, str] = {}


# ---------------------------------------------------------------------------
# ตรวจภาษา — ไม่เรียก LLM
# ---------------------------------------------------------------------------

def thai_ratio(text: str) -> float:
    """สัดส่วนอักษรไทย เทียบกับตัวอักษรทั้งหมดที่เป็นตัวหนังสือ

    นับแค่ตัวหนังสือ (ข้าม ตัวเลข ช่องว่าง เครื่องหมาย) เพราะ "เคส iPhone 15"
    ควรถูกมองว่าเป็นไทยผสม ไม่ใช่อังกฤษเพราะมีเลข 15 อยู่
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    thai = sum(1 for c in letters if THAI_START <= ord(c) <= THAI_END)
    return thai / len(letters)


def detect_language(text: str) -> str:
    """คืน "th" ถ้ามีอักษรไทยอยู่เลย ไม่งั้น "en"

    ใช้เกณฑ์ "มีอักษรไทยแม้ตัวเดียว" ไม่ใช่ "ไทยเกินครึ่ง" เพราะ "เคส iPhone 15"
    ก็ยังต้องแปล — คำว่า "เคส" คือตัวที่บอกว่าผู้ใช้ต้องการสินค้าชนิดไหน
    """
    return "th" if thai_ratio(text) > 0 else "en"


def _clean_output(raw: str, fallback: str) -> str:
    """เก็บเฉพาะคำค้นภาษาอังกฤษ ถ้าเอาไม่ได้ให้คืนคำค้นเดิม

    โมเดลขนาด 8B มักเติมคำอธิบายหรือเครื่องหมายคำพูดมาด้วย
    ถ้าผลที่ได้ยังมีอักษรไทยหรือว่างเปล่า แปลว่าแปลไม่สำเร็จ -> คืนของเดิม
    (ค้นด้วยไทยยังได้ผลบางส่วน ดีกว่าค้นด้วยข้อความพัง)
    """
    text = raw.strip().split("\n")[0].strip()
    for mark in ('"', "'", "`", "“", "”", "«", "»"):
        text = text.strip(mark)
    # ตัดคำนำหน้าที่โมเดลชอบเติม
    for prefix in ("->", "คำแปล:", "แปลว่า:", "Translation:", "English:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    text = text.strip().strip(".")

    if not text or thai_ratio(text) > 0 or len(text) > MAX_CHARS:
        return fallback
    return text


def translate(text: str, model: str = CHAT_MODEL) -> str:
    """แปลไทย → อังกฤษ ด้วย LLM · คืนคำค้นเดิมถ้าแปลไม่สำเร็จ

    temperature = 0 เพื่อให้ถามซ้ำได้คำตอบเดิม (สำคัญต่อความถูกต้องของผลเทียบ)
    """
    key = text.strip()
    if key in _CACHE:
        return _CACHE[key]

    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "stream": False,
                  "options": {"temperature": 0, "seed": 0},
                  "messages": [{"role": "system", "content": TRANSLATE_SYSTEM},
                               {"role": "user", "content": key}]},
            timeout=TIMEOUT)
        response.raise_for_status()
        raw = response.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError):
        # ต่อ Ollama ไม่ได้หรือโมเดลตอบผิดรูป -> ค้นด้วยไทยไปก่อน ไม่ทำให้ระบบล้ม
        return key

    result = _clean_output(raw, fallback=key)
    _CACHE[key] = result
    return result


# ---------------------------------------------------------------------------
# หน้าตาที่สถาปัตยกรรมเรียกใช้
# ---------------------------------------------------------------------------

@dataclass
class QueryPlan:
    """คำค้นที่เตรียมพร้อมค้นแล้ว + ร่องรอยว่าทำอะไรไปบ้าง"""
    original: str
    language: str                # "th" | "en"
    search_text: str             # ข้อความที่จะส่งเข้า search() จริง
    translated: str | None       # None ถ้าไม่ได้แปล
    used_llm: bool
    from_cache: bool = False

    def trace(self) -> dict:
        return {"original": self.original, "language": self.language,
                "search_text": self.search_text, "used_llm": self.used_llm,
                "from_cache": self.from_cache}


def prepare_query(text: str, model: str = CHAT_MODEL) -> QueryPlan:
    """ตรวจภาษาแล้วแปลถ้าจำเป็น — **คำถามอังกฤษไม่เรียก LLM เลย**

        >>> prepare_query("cheap yoga mat").used_llm
        False
        >>> plan = prepare_query("เสื่อโยคะกันลื่น")
        >>> plan.search_text
        'non-slip yoga mat'
    """
    original = text.strip()
    if detect_language(original) == "en":
        return QueryPlan(original=original, language="en", search_text=original,
                         translated=None, used_llm=False)

    cached = original in _CACHE
    english = translate(original, model)
    failed = english == original            # แปลไม่สำเร็จ -> ค้นด้วยไทยไปก่อน
    return QueryPlan(original=original, language="th", search_text=english,
                     translated=None if failed else english,
                     used_llm=not cached, from_cache=cached)


def search(retriever, query: str, k: int = 100, where: dict | None = None,
           model: str = CHAT_MODEL):
    """`search()` ที่รองรับสองภาษา — คืน (ผลค้น, QueryPlan)

    ทุกแขนต้องเรียกตัวนี้ตัวเดียวกัน (mark7 มี A1 กับ A3) ไม่ใช่เรียก
    `Retriever.search()` ตรง ๆ ไม่งั้นแขนที่ลืมแปลจะเสียเปรียบและผลเทียบจะไม่แฟร์

        >>> with Retriever() as r:
        ...     hits, plan = search(r, "เสื่อโยคะกันลื่น", k=100)
    """
    plan = prepare_query(query, model)
    hits = retriever.search(plan.search_text, k=k, where=where)
    return hits, plan


def clear_cache() -> None:
    """ล้างคำแปลที่จำไว้ — ใช้ตอนวัดผลเพื่อให้แต่ละรอบเริ่มจากศูนย์เท่ากัน"""
    _CACHE.clear()
