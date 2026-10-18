"""โมดูล Memory — จำว่าผู้ใช้ต้องการอะไร ข้ามรอบสนทนา

**เป็นชิ้นส่วนร่วมของทั้ง A1 และ A3** — ตั้งแต่ปรับ A1 ให้ตรงโครง RAG 5 ขั้น (ขั้น 133)
ความจำคือ "ขั้น 2 Understand User Context" ซึ่งโครงกำหนดให้ RAG มาตรฐานต้องมี

เก็บความต้องการเป็น **โปรไฟล์ 9 ช่อง** ที่สะสมขึ้นเรื่อย ๆ ไม่ใช่เก็บแค่ข้อความล่าสุด
เพราะผู้ใช้จริงบอกความต้องการกระจายหลายรอบ:

    รอบ 1  "อยากได้หูฟัง"              -> category = หูฟัง
    รอบ 2  "งบไม่เกิน 30"              -> budget_max = 30   (ยังจำ category ไว้)
    รอบ 3  "ไม่เอา Sony"               -> brands_disliked = [Sony]  (ยังจำสองอันแรก)

ถ้าค้นด้วยข้อความล่าสุดอย่างเดียว รอบ 3 จะกลายเป็นการค้นคำว่า "ไม่เอา Sony"
ซึ่งไม่มีความหมาย → **ต้องค้นด้วยโปรไฟล์ที่สะสมไว้** ดู `profile_to_query()`

ย้ายมาจาก `agentic-rag-demo/agentic_rag.py` ส่วน `update_profile()` และ `build_query()`
ปรับให้คืน `MemoryUpdate` ที่บอกว่าเปลี่ยนอะไรไป เพื่อให้ตรวจย้อนได้

**สิ่งที่ A3/A4 จะเพิ่มทีหลัง:** บันทึกคำค้นที่ลองไปแล้วในรอบนี้ (`tried_queries`)
ไม่งั้นลูปรอบ 2 จะค้นคำเดิมได้ผลเดิม — เตรียมช่องไว้แล้วแต่ A2 ยังไม่ใช้

⚠ ต้องสตาร์ต Ollama ก่อน:  ollama.exe serve
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed import OLLAMA_URL                                     # noqa: E402
from rerank import Constraints                                   # noqa: E402
from translate import CHAT_MODEL                                 # noqa: E402

TIMEOUT = 180
HISTORY_TURNS = 4            # ส่งบทสนทนาย้อนหลังกี่รอบให้โมเดลอ่าน

# ⚠ ช่องที่ **ห้ามให้ LLM ตั้งค่า** — ต้องให้โค้ดตั้งเท่านั้น
#
# พบจากการทดสอบคุย 4 รอบ (ขั้น 5.5): รอบที่ 4 ผู้ใช้พิมพ์แค่ "งบไม่เกิน 25 ดอลลาร์"
# แต่ LLM เอา **ชื่อสินค้า 3 ชิ้นที่ระบบเพิ่งแนะนำไป** ใส่ใน rejected_titles
# ทั้งที่ผู้ใช้ไม่ได้ปฏิเสธอะไรเลย — มันอ่านคำตอบของผู้ช่วยในประวัติสนทนา
# แล้วตีความว่าเป็นของที่ถูกปฏิเสธ
#
# ผลเสียจริง: ชื่อพวกนั้นถูกส่งต่อเป็น Constraints.titles_rejected -> Reranker ชั้นที่ 1
# ตัดทิ้ง → **สินค้าที่เคยแนะนำจะถูกแบนทุกรอบถัดไป** คลังจะหดลงเรื่อย ๆ โดยไม่มีเหตุผล
#
# ทำไมไม่แก้ด้วยการเขียนกฎในพรอมต์: ขั้น 5.2 วัดแล้วว่าโมเดลขนาดนี้ไม่ทำตามกฎในพรอมต์
# (เมินตัวอย่างที่ตรงทุกตัวอักษร · ละเมิดกฎที่เขียนไว้) → กันด้วยโค้ดแน่นอนกว่า
#
# แขนที่ต้องการบันทึกว่าผู้ใช้ปฏิเสธสินค้าชิ้นไหน ให้เติม profile.rejected_titles เองตรง ๆ
LLM_MUST_NOT_SET = frozenset({"rejected_titles"})

# 28 หมวดของคลังสินค้า (ตัด "Unknown" ออก) — **ต้องตรงกับค่าในคอลัมน์ category**
# ใช้เป็นรายการปิดให้ LLM เลือก แล้วส่งต่อให้ Reranker ใช้เป็นสัญญาณจัดอันดับ
# ไม่ใช่ตัวกรอง — ของนอกหมวดยังมีสิทธิ์ถ้าสัญญาณอื่นดีพอ
CATALOG_CATEGORIES = (
    "Amazon Fashion", "Appliances", "Arts Crafts and Sewing", "Automotive",
    "Baby Products", "Beauty and Personal Care", "Books", "CDs and Vinyl",
    "Cell Phones and Accessories", "Clothing Shoes and Jewelry", "Digital Music",
    "Electronics", "Gift Cards", "Grocery and Gourmet Food", "Handmade Products",
    "Health and Household", "Health and Personal Care", "Home and Kitchen",
    "Industrial and Scientific", "Musical Instruments", "Office Products",
    "Patio Lawn and Garden", "Pet Supplies", "Software", "Sports and Outdoors",
    "Tools and Home Improvement", "Toys and Games", "Video Games",
)

EXTRACT_SYSTEM = f"""คุณคือระบบสกัดความต้องการจากบทสนทนาแนะนำสินค้า
อ่านข้อความล่าสุดของผู้ใช้ แล้วอัปเดตโปรไฟล์เดิม — คงของเดิมไว้ แก้เฉพาะที่ผู้ใช้บอกใหม่

- budget_max เป็นตัวเลขล้วน เช่น "งบไม่เกิน 30 ดอลลาร์" -> 30 · ถ้าไม่ระบุให้คงค่าเดิม
- ใส่เฉพาะที่ผู้ใช้พูดจริง ห้ามเดา
- ถ้าผู้ใช้ตอบว่า "ไม่มี" หรือ "อะไรก็ได้" อย่าเพิ่มอะไร
- category = ชนิดสินค้าตามคำของผู้ใช้ เช่น "หูฟังบลูทูธ" (เขียนอิสระได้)
- catalog_category = หมวดในคลังที่สินค้านั้นน่าจะอยู่ **เลือกจากรายการนี้เท่านั้น**
  {" · ".join(CATALOG_CATEGORIES)}
  ข้อนี้ให้จัดหมวดได้ ไม่ถือว่าเป็นการเดา · **ถ้าไม่มั่นใจหรือยังไม่รู้ว่าผู้ใช้หาอะไร ให้ตอบ ""**

ตอบเป็น JSON โครงเดียวกับโปรไฟล์เท่านั้น"""


@dataclass
class Profile:
    """ความต้องการของผู้ใช้ **9 ช่อง** — A1 กับ A3 ใช้โครงเดียวกันเพื่อให้เทียบกันได้

    เดิมมี 8 ช่อง · `catalog_category` เพิ่มเข้ามาตอนขั้น 124 ให้เป็นสัญญาณของ Reranker
    """
    category: str = ""
    catalog_category: str = ""    # 1 ใน CATALOG_CATEGORIES — ใช้เป็นสัญญาณใน Reranker
    budget_max: float | None = None
    brands_liked: list[str] = field(default_factory=list)
    brands_disliked: list[str] = field(default_factory=list)
    features_wanted: list[str] = field(default_factory=list)
    use_case: str = ""
    rejected_titles: list[str] = field(default_factory=list)
    other_preferences: str = ""

    # A3/A4 ใช้ — A2 ไม่แตะ
    tried_queries: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """ยังไม่รู้อะไรเลยเกี่ยวกับสิ่งที่ผู้ใช้อยากได้"""
        return not any((self.category, self.use_case, self.features_wanted,
                        self.budget_max, self.brands_liked))

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "tried_queries"}

    def to_constraints(self) -> Constraints:
        """แปลงเป็นเงื่อนไขให้ Reranker ชั้นที่ 1 เอาไปตัดของที่ผิดเงื่อนไข

        **นี่คือจุดที่ความจำเชื่อมกับการคัดเลือก** — ⚠ **A1 รุ่นเดิม**ไม่มีส่วนนี้
        จึงแนะนำของราคา $46.98 ตอนผู้ใช้บอกงบ $20 (ดูขั้น 5.3) · **A1 รุ่นปัจจุบัน
        มีส่วนนี้แล้ว** ตั้งแต่ขั้น 133 จึงกรองงบได้เหมือน A3 — หลักฐานเดิมยังอ้างได้
        ในฐานะผลของ Naive RAG ที่ไม่มีชั้นคัดเลือก
        """
        return Constraints(budget_max=self.budget_max,
                           category=self.catalog_category or None,
                           stores_excluded=list(self.brands_disliked),
                           titles_rejected=list(self.rejected_titles))


@dataclass
class MemoryUpdate:
    """ผลการอัปเดต + บอกว่าเปลี่ยนอะไรไป เพื่อให้ตรวจย้อนได้"""
    profile: Profile
    changed: list[str] = field(default_factory=list)
    llm_calls: int = 0

    def trace(self) -> dict:
        return {"changed": self.changed, "llm_calls": self.llm_calls,
                "profile": self.profile.to_dict()}


# ลำดับการ "ขยายคำค้น" ตอนค้นใหม่ — ใช้โดย A3/A4
#
# ทำไมต้องมี: ถ้าลูปค้นด้วยคำเดิมก็ได้ผลเดิม วนเท่าไหร่ก็ไม่ดีขึ้น
# ทำไมขยายให้กว้างขึ้น (ไม่ใช่แคบลง): การค้นไม่เจอมักเกิดจากคำค้นเจาะจงเกินไป
# เช่น "เสื่อโยคะ กันลื่น หนา 6 มม พกพา" แคบจนไม่มีของตรง → ตัดคำขยายออกทีละชั้น
#
# ชั้น 0  หมวด + การใช้งาน + คุณสมบัติ + แบรนด์ที่ชอบ + อื่น ๆ   (แคบสุด)
# ชั้น 1  หมวด + การใช้งาน + แบรนด์ที่ชอบ
# ชั้น 2  หมวด (หรือการใช้งานถ้าไม่มีหมวด)                      (กว้างสุด)
# ชั้น 3+ ไม่มีให้ขยายอีก -> คืน None เพื่อบอกลูปว่าหมดทางแล้ว
#
# **A3 ใช้บันไดนี้ล้วน ๆ ไม่เรียก LLM เลย** จึงทำซ้ำได้ 100%
MAX_BROADEN = 2

# ตัดวลีบอกงบออกจากข้อความก่อนเอาไปค้น — ตัวเลขงบถูกเก็บไว้ใน Profile แล้ว
# จึงไม่สูญเงื่อนไข · รองรับทั้งไทยและอังกฤษเพราะคำค้นไทยผ่านชั้นแปลก่อนค้น
# ⚠ ต้องไม่กินตัวเลขที่เป็นสเปกสินค้า: "usb flash drive 2 tb under $27"
#   ต้องเหลือ "usb flash drive 2 tb" ไม่ใช่ "usb flash drive"
_BUDGET_PHRASE = re.compile(
    r"\s*(?:,|\.)?\s*(?:"
    r"(?:under|below|less\s+than|within|up\s+to|max(?:imum)?|cheaper\s+than|budget)"
    r"\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*(?:dollars?|usd|บาท)?"
    r"|\$\s*\d[\d,]*(?:\.\d+)?\s*(?:or\s+less|and\s+under)"
    r"|(?:ไม่เกิน|ต่ำกว่า|ราคาไม่เกิน|ในงบ|งบประมาณ|งบ)\s*\$?\s*"
    r"\d[\d,]*(?:\.\d+)?\s*(?:ดอลลาร์|บาท|usd)?"
    r")", re.IGNORECASE)


def strip_budget(text: str) -> str:
    """ตัดวลีบอกงบออก คืนข้อความที่เหลือ

        >>> strip_budget("usb flash drive 2 tb under $27")
        'usb flash drive 2 tb'
        >>> strip_budget("แผ่นกันสุนัขขึ้น ไม่เกิน 11 ดอลลาร์")
        'แผ่นกันสุนัขขึ้น'
        >>> strip_budget("led light strip")
        'led light strip'
    """
    return " ".join(_BUDGET_PHRASE.sub(" ", text).split()).strip()


def profile_to_query(profile: Profile, user_message: str,
                     broaden: int = 0) -> str | None:
    """สร้างคำค้นจาก**คำของผู้ใช้ + โปรไฟล์ที่สะสมไว้เป็นส่วนเสริม**

    ชั้น 0  คำของผู้ใช้เอง + สิ่งที่สะสมจากเทิร์นก่อนที่ยังไม่มีในคำนั้น  (แคบสุด)
    ชั้น 1  หมวด + การใช้งาน + แบรนด์ที่ชอบ  (สรุปจากโปรไฟล์ ทิ้งคำของผู้ใช้)
    ชั้น 2  หมวด หรือ การใช้งาน                                        (กว้างสุด)
    ไม่ใส่ budget กับ brands_disliked ลงในคำค้น เพราะเป็น**เงื่อนไขตัดทิ้ง**
    ที่ Reranker ชั้นที่ 1 จัดการ — ใส่ลงคำค้นจะทำให้เวกเตอร์เพี้ยน
    (คำว่า "ไม่เอา Sony" ทำให้โมเดลค้นเจอ Sony มากขึ้น ไม่ใช่น้อยลง)

    `broaden` คือชั้นการขยายคำค้นตอนค้นใหม่ · คืน `None` เมื่อไม่มีอะไรให้ขยายอีก

        >>> p = Profile(category="เสื่อโยคะ", features_wanted=["กันลื่น", "หนา"])
        >>> profile_to_query(p, "เสื่อโยคะ หนา 6 มม", 0)   # คำผู้ใช้มาก่อน
        'เสื่อโยคะ หนา 6 มม กันลื่น'
        >>> profile_to_query(p, "", 0)                      # ไม่มีข้อความ -> ใช้โปรไฟล์
        'เสื่อโยคะ กันลื่น หนา'
        >>> profile_to_query(p, "", 1)
        'เสื่อโยคะ'
    """
    if broaden > MAX_BROADEN:
        return None

    if broaden >= 2:
        core = profile.category or profile.use_case
        return core or None

    # ชั้น 0 — **คำของผู้ใช้เป็นหลัก โปรไฟล์เป็นส่วนเสริม ห้ามเป็นส่วนแทน**
    #
    # ⚠ **แต่ต้องตัดงบออกก่อน** — วัดได้ว่าหลุดเข้าคำค้น **30/30 ข้อทั้งสองภาษา**
    #     "scat mats for dogs under $11"      -> ค้นด้วย "...under $11"
    #     "แผ่นกันสุนัขขึ้น ไม่เกิน 11 ดอลลาร์" -> ค้นด้วย "dog guard mat under $11"
    # เป็นผลข้างเคียงของการแก้ครั้งก่อน: พอเอาคำของผู้ใช้มาเป็นฐาน งบก็ติดมาด้วย
    # (โค้ดเดิมประกอบจากโปรไฟล์ล้วนจึงไม่มีปัญหา เพราะตั้งใจไม่ใส่ budget)
    # งบเป็นเงื่อนไขตัดทิ้งที่ Reranker ชั้น 1 จัดการ ใส่ลงคำค้นมีแต่ทำให้เวกเตอร์เพี้ยน
    #
    # ⚠ โค้ดเดิมสร้างคำค้นจากโปรไฟล์ล้วน ทำให้คำของผู้ใช้หายไปก่อนค้น
    # วัดจากคำค้นกลุ่ม 1 จำนวน 20 คำ **สูญข้อมูล 14 คำ (70%)** เช่น
    #     usb flash drive 2 tb   -> usb flash drive          (หาย "2 tb")
    #     scat mats for dogs     -> dog accessories odor control
    #     reflective cat harness -> pet accessories reflective
    # คลังมีไดรฟ์ 2TB อยู่อันดับ 1-3 ถ้าค้นด้วยคำเดิม แต่ระบบไม่เคยได้เห็น
    # (ความผิดพลาดชนิดเดียวกับขั้นที่ 6 "ค้อนหงอน -> เครื่องมือ" ซึ่งตอนนั้น
    #  แก้แค่ชั้นเขียนคำค้นใหม่ระหว่างวนรอบ **คำค้นรอบแรกยังพังอยู่**)
    if broaden == 0 and strip_budget(user_message):
        msg = strip_budget(user_message)
        low = msg.lower()
        out = [msg]
        for extra in (profile.use_case, *profile.features_wanted,
                      *profile.brands_liked, profile.other_preferences):
            if extra and extra.lower() not in low:   # เติมเฉพาะที่ยังไม่มีในคำผู้ใช้
                out.append(extra)
        return " ".join(out)

    parts: list[str] = []
    if profile.category:
        parts.append(profile.category)
    if profile.use_case:
        parts.append(profile.use_case)
    if broaden == 0 and profile.features_wanted:
        parts.extend(profile.features_wanted)
    if profile.brands_liked:
        parts.extend(profile.brands_liked)
    if broaden == 0 and profile.other_preferences:
        parts.append(profile.other_preferences)

    if parts:
        return " ".join(parts)
    # โปรไฟล์ว่าง — ใช้ข้อความของผู้ใช้ได้แค่ชั้น 0 เพราะไม่มีอะไรให้ตัดออก
    return user_message.strip() if broaden == 0 else None


def _chat_json(system: str, user: str, model: str = CHAT_MODEL) -> dict:
    """เรียก LLM แบบบังคับให้ตอบ JSON · คืน {} ถ้าพลาด (ผู้เรียกต้องมีทางสำรอง)"""
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat", timeout=TIMEOUT,
            json={"model": model, "stream": False, "format": "json",
                  "options": {"temperature": 0, "seed": 0},
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}]})
        response.raise_for_status()
        return json.loads(response.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
        return {}


def update(profile: Profile, user_message: str,
           history: list[dict] | None = None,
           model: str = CHAT_MODEL) -> MemoryUpdate:
    """อ่านข้อความล่าสุดแล้วอัปเดตโปรไฟล์

    **รับเฉพาะค่าที่ชนิดข้อมูลตรงกับที่ประกาศไว้** — โมเดลตอบผิดชนิดบ่อย
    (เช่น budget_max เป็นสตริง "30 ดอลลาร์" หรือ brands_liked เป็นสตริงเดี่ยว)
    ถ้าไม่กรองไว้ โปรไฟล์จะพังเงียบ ๆ แล้วไปโผล่เป็นบั๊กที่ Reranker

        >>> p = Profile()
        >>> up = update(p, "อยากได้หูฟังบลูทูธ งบไม่เกิน 30 ดอลลาร์")
        >>> up.profile.budget_max
        30.0
    """
    history = history or []
    convo = "\n".join(f"{h['role']}: {h['content']}"
                      for h in history[-HISTORY_TURNS:])
    user = (f"โปรไฟล์ปัจจุบัน: {json.dumps(profile.to_dict(), ensure_ascii=False)}\n"
            f"บทสนทนาก่อนหน้า:\n{convo}\n\n"
            f'ข้อความล่าสุด: "{user_message}"\nอัปเดตโปรไฟล์')

    result = _chat_json(EXTRACT_SYSTEM, user, model)
    changed: list[str] = []

    for key, current in profile.to_dict().items():
        if key not in result or key in LLM_MUST_NOT_SET:
            continue
        value = result[key]

        if key == "budget_max":
            if isinstance(value, bool):          # bool เป็น int ใน Python ต้องกันก่อน
                continue
            if isinstance(value, (int, float)) and value > 0:
                if float(value) != current:
                    profile.budget_max = float(value)
                    changed.append(key)
            continue

        if isinstance(current, list):
            if isinstance(value, list):
                clean = [str(v).strip() for v in value if str(v).strip()]
                if clean != current:
                    setattr(profile, key, clean)
                    changed.append(key)
            continue

        if key == "catalog_category":
            # **รับเฉพาะค่าที่อยู่ในรายการจริง** — โมเดลแต่งชื่อหมวดเองได้ง่ายมาก
            # เทียบแบบไม่สนตัวพิมพ์ แล้วเก็บด้วยสะกดมาตรฐานของคลัง
            if not isinstance(value, str):
                continue
            match = next((c for c in CATALOG_CATEGORIES
                          if c.lower() == value.strip().lower()), "")
            if match and match != current:
                profile.catalog_category = match
                changed.append(key)
            continue

        if isinstance(value, str) and value.strip() and value.strip() != current:
            setattr(profile, key, value.strip())
            changed.append(key)

    return MemoryUpdate(profile=profile, changed=changed, llm_calls=1)
