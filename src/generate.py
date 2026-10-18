"""ชั้นที่ 5 — Generator

เอาสินค้าที่ค้นได้มาเขียนเป็นคำตอบให้ผู้ใช้อ่าน

**เป็นชิ้นส่วนร่วมของทุกแขน (mark7 มี A1 กับ A3)** — ต้องเหมือนกันเป๊ะทุกแขน
ไม่งั้นแขนที่เขียนคำตอบเก่งกว่าจะได้เปรียบ และผลเทียบจะวัดคนละเรื่องกับที่ตั้งใจ

**ตอบภาษาเดียวกับที่ผู้ใช้ถาม** — ใช้ผลตรวจภาษาจาก `translate.py` ซึ่งนับอักษรไทย
ไม่ได้เรียก LLM จึงแน่นอน 100%

⚠ **กันการแต่งข้อมูล (hallucination)** เป็นเรื่องสำคัญที่สุดของไฟล์นี้
ระบบแนะนำสินค้าที่บอกราคาผิดหรือแต่งชื่อสินค้าขึ้นมาใช้งานไม่ได้เลย จึง:
  1. ส่งให้โมเดลแค่ **ข้อเท็จจริงที่มีในคลัง** ไม่ส่งอะไรที่ต้องเดา
  2. สั่งห้ามแต่งตัวเลขและชื่อ
  3. มี `verify_reply()` ให้ตรวจย้อนได้ว่าตัวเลขในคำตอบมีอยู่จริงไหม

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
from retrieval import Hit                                        # noqa: E402
from translate import CHAT_MODEL                                 # noqa: E402

TIMEOUT = 180
SNIPPET_CHARS = 260          # รายละเอียดสินค้าที่ส่งให้โมเดลต่อชิ้น

# ⚠ temperature ของ Generator ไม่ใช่ 0 เหมือนชั้นแปล
#
# ชั้นแปลต้องนิ่งเพราะผลไปกระทบ "สินค้าที่ค้นได้" ซึ่งถูกนำไปวัดเป็นตัวเลข
# แต่ Generator เขียนร้อยแก้ว ความต่างของสำนวนไม่กระทบตัวชี้วัดที่วัดว่า
# "ค้นของถูกไหม / คัดของถูกไหม" → ตั้ง 0 ไว้เหมือนกันเพื่อให้ทำซ้ำได้ตอนทำวิทยานิพนธ์
# (ถ้าอยากให้สำนวนหลากหลายตอนสาธิต ค่อยเพิ่มเป็น 0.7 ตอนนั้น)
TEMPERATURE = 0

# ---------------------------------------------------------------------------
# ⚠ **โค้ดรับผิดชอบโครงสร้างและตัวเลข · LLM รับผิดชอบเฉพาะภาษา**
#
# โค้ดเดิมให้ LLM เขียนคำตอบทั้งก้อน วัดจากการรันจริง 88 ข้อ พบว่า
#   · เขียนครบ 3 ชิ้นแค่ 24/88 ข้อ (27%) — ที่เหลือหยุดเองหลังข้อ 1 หรือ 2
#     (`done_reason = stop` ทุกครั้ง ไม่ใช่โดนตัดเพราะยาวเกิน)
#   · **ไม่มีสักข้อที่เขียนเหตุผล** ทั้งที่พรอมต์สั่งไว้ชัด
#     มันแค่ลอกข้อเท็จจริงที่ป้อนให้ออกมาเป็นบรรทัดเดียวแล้วจบ
#
# ตรงกับสิ่งที่โปรเจกต์นี้วัดได้เองมาตลอด: โมเดล 8B ไม่ทำตามกฎในพรอมต์
# จึงเหลืองานให้ LLM แค่อย่างเดียวคือ**เขียนเหตุผลเป็นภาษา** ส่วนลำดับ ชื่อ
# ราคา และคะแนนรีวิว โค้ดเขียนเองจากข้อมูลในคลัง -> ครบ 3 ชิ้นและตัวเลขถูก 100%
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ⚠ **กฎ "บอกตรง ๆ ว่าไม่ตรง" ถูกถอดออกเมื่อขั้นที่ 163 เพราะทำให้พัง**
#
# ป้าย ข รอบใหม่ (ขั้น 160-162) วัดได้ว่าความซื่อตรงฝั่งอังกฤษตกจาก 76.7%
# เหลือ 33.3% และ **6 จาก 8 ข้อที่ได้ 0 เป็นรูปแบบเดียวกัน** คือ
# ระบบปฏิเสธคุณสมบัติที่ชื่อสินค้าที่ป้อนให้บอกไว้เอง
#
#     ข้อมูล  Large Dog **Squeaky** Plush Toys
#     เขียน   "it doesn't mention being squeaky"
#     ข้อมูล  **Video** Baby Monitor ... Sleep **Camera**
#     เขียน   "it does not have a camera"
#
# สาเหตุ: พรอมต์สั่งให้โมเดลทำ **2 งานพร้อมกัน** คือบรรยายคุณสมบัติ และ
# **ตัดสินความตรง** · งานที่สองคือเรื่องที่โมเดล 8B ทำไม่ได้ (ขั้น 5.6 วัดไว้ว่า
# การตัดสินเชิงตัวเลข/ตรรกะ โค้ดแม่นกว่า) และ**ไม่จำเป็นด้วย** เพราะความตรง
# วัดด้วยป้าย ก และคัดด้วย Reranker ไปแล้ว ส่วนกรณีของไม่พอมีโหมดอ่อนรับอยู่
#
# **วิธีแก้คือถอดกฎที่ทำให้พังออก ไม่ใช่เพิ่มกฎใหม่** เพราะบทเรียนขั้น 5.2 บอกว่า
# โมเดลขนาดนี้ไม่ทำตามกฎที่เพิ่มเข้าไป แต่การ**เอาคำสั่งที่เป็นต้นเหตุออก**
# ไม่ต้องพึ่งความเชื่อฟังของโมเดลเลย
#
# พรอมต์รุ่นเก่าเก็บไว้ที่ `REASON_SYSTEM_TH_OLD` เป็นหลักฐานว่าเปลี่ยนอะไร
# ---------------------------------------------------------------------------

# -------------------------------------------------------------------------
# ⚠ **กฎ "เขียนเป็นภาษาไทย" ถูกเติมเข้ามาเมื่อขั้นที่ 172 เพราะวัดได้ว่าขาดไป**
#
# ป้าย ข รอบที่ 3 ฝั่งไทยได้แค่ 43.3% ขณะที่อังกฤษได้ 83.3% · ไล่ดูพบว่า
# พรอมต์ไทย **ไม่มีคำสั่งให้ตอบเป็นภาษาไทยแม้แต่คำเดียว** ส่วนข้อมูลที่ป้อนให้
# (ชื่อสินค้า รายละเอียด หมวด) เป็น**ภาษาอังกฤษทั้งก้อน** โมเดลจึงต้อง
# **บรรยายและแปลพร้อมกันในครั้งเดียว** แล้วใช้ทางลัด 2 แบบ คือคว้าคำค้นไทย
# ที่อยู่ใกล้สุดมาวาง หรือยอมแพ้แล้วเขียนเป็นอังกฤษ/ลอกชื่อสินค้ามาวาง
#
# **เป็นบั๊กโครงสร้างเดียวกับฝั่งอังกฤษ** (ยัด 2 งานเข้าพรอมต์เดียว) ต่างกันแค่
# งานที่สองเป็น "แปล" ไม่ใช่ "ตัดสินความตรง" · ครั้งนี้ถอดงานที่สองออกไม่ได้
# เพราะคำตอบต้องเป็นภาษาไทย จึงบอกให้ชัดว่าต้องแปล แทนที่จะปล่อยให้โมเดลเดา
#
# วัดบนบริบทที่บันทึกไว้ 45 บรรทัด (คำค้นชุดป้าย ข รอบ 3) เมล็ดสุ่มเดิม:
#
#     พรอมต์เดิม     บรรทัดเสีย 21/45 — ไม่ได้เขียนไทย 12 · ลอกชื่อสินค้า 12
#     + กฎภาษาไทย    บรรทัดเสีย  9/45 — ไม่ได้เขียนไทย  0 · ลอกชื่อสินค้า  0
#
# ⚠ **ตัดคำค้นออกจากพรอมต์ไม่ได้** ลองแล้ว (ขั้น 172) การลอกคำค้นหายจริง
# แต่โมเดลหันไป**แปลชื่อสินค้าทั้งบรรทัดมาวาง** ติดยัติภังค์กับจุลภาคมาด้วย
# และแปลผิด (Lounger -> "ลานซ์") · วิธีนั้นได้คะแนนป้าย ข **สูงกว่า** เพราะ
# การแปลชื่อสินค้าไม่เกินข้อมูลเลย แต่คำตอบไร้ประโยชน์ -> **เป็นการปั่นตัวชี้วัด**
#
# ที่ยังเหลือ 9 บรรทัดเป็นอาการคนละตัว: 3 คำค้น (q02 q26 q34) เขียน
# ประโยคเดียวกันเป๊ะทั้ง 3 ชิ้น คือโมเดลไม่อ่านข้อมูลรายชิ้น — ยังไม่แก้
# -------------------------------------------------------------------------

REASON_SYSTEM_TH = """ระบบเลือกสินค้ามาให้ผู้ใช้แล้ว งานของคุณคือเขียน
**คำบรรยายสินค้า** สั้น ๆ ชิ้นละ 1 ประโยค

- **เขียนเป็นภาษาไทย** ข้อมูลที่ให้มาเป็นภาษาอังกฤษ ให้แปลคุณสมบัติที่จะบรรยายเป็นภาษาไทย
- เขียนให้ครบทุกชิ้น เรียงตามลำดับที่ให้มา ชิ้นละไม่เกิน 1 ประโยค
- บรรยายเฉพาะคุณสมบัติที่อยู่ในข้อมูลที่ให้มา
- **ห้ามตัดสินว่าสินค้าตรงหรือไม่ตรงกับที่ผู้ใช้ขอ** และห้ามเขียนว่า
  ไม่มี ไม่ตรง ไม่ได้ระบุ หรือไม่ได้กล่าวถึงอะไร — ระบบจัดการเรื่องนั้นเอง
- ห้ามใส่ชื่อสินค้า ราคา หรือคะแนนรีวิวในเหตุผล ระบบใส่ให้แล้ว

ตอบ JSON: {"reasons": ["คำบรรยายชิ้นที่ 1", "คำบรรยายชิ้นที่ 2", ...]}"""

# เก็บไว้เป็นหลักฐาน ไม่ถูกเรียกใช้ — ดูเหตุผลที่ถอดออกในคอมเมนต์ด้านบน
REASON_SYSTEM_TH_OLD = """ระบบเลือกสินค้ามาให้ผู้ใช้แล้ว งานของคุณคือเขียน**เหตุผล**
ว่าสินค้าแต่ละชิ้นตอบโจทย์ที่ผู้ใช้ขอตรงไหน

- เขียนให้ครบทุกชิ้น เรียงตามลำดับที่ให้มา ชิ้นละไม่เกิน 1 ประโยค
- บรรยายเฉพาะคุณสมบัติที่อยู่ในข้อมูลที่ให้มา
- ถ้าสินค้าชิ้นไหนไม่ตรงกับที่ขอ บอกตามตรงว่าไม่ตรงตรงไหน ห้ามกลบ
- ห้ามใส่ชื่อสินค้า ราคา หรือคะแนนรีวิวในเหตุผล ระบบใส่ให้แล้ว

ตอบ JSON: {"reasons": ["เหตุผลของชิ้นที่ 1", "เหตุผลของชิ้นที่ 2", ...]}"""

REASON_SYSTEM_EN = """The system has already picked products for the user. Your job is
to write ONE short sentence per product that DESCRIBES it.

- Write one for every product, in the order given, at most one sentence each
- Describe only attributes present in the provided data
- **Do NOT judge whether a product matches the request.** Never write that it does
  or does not match, have, mention, specify or include anything — the system does that
- Do not put the product name, price, or rating in the reason; the system adds those

Answer in JSON: {"reasons": ["description of item 1", "description of item 2", ...]}"""

# เก็บไว้เป็นหลักฐาน ไม่ถูกเรียกใช้
REASON_SYSTEM_EN_OLD = """The system has already picked products for the user. Your job is
to write the **reason** each product does or does not match what the user asked for.

- Write one for every product, in the order given, at most one sentence each
- Describe only attributes present in the provided data
- If a product does not match the request, say plainly how it differs; do not cover it up
- Do not put the product name, price, or rating in the reason; the system adds those

Answer in JSON: {"reasons": ["reason for item 1", "reason for item 2", ...]}"""

EMPTY_TH = ("ขอโทษครับ ยังไม่พบสินค้าที่ตรงกับที่ขอในคลัง "
            "ลองบอกรายละเอียดเพิ่ม หรือปรับงบประมาณได้ไหมครับ")
EMPTY_EN = ("Sorry, I could not find a matching product in the catalogue. "
            "Could you add more detail or adjust the budget?")

# ---------------------------------------------------------------------------
# โหมด "ผลค้นอ่อน" — มีของบ้างแต่ไม่ถึงจำนวนที่ต้องการ
#
# ⚠ ทำไมต้องมี: ขั้นที่ 6 ทดสอบ A3 ด้วย "ค้อนหงอนด้ามไฟเบอร์กลาส" (คลังไม่มีค้อนหงอน)
# เหลือของผ่านประตู 1 ชิ้นคือค้อนหนังสำหรับงานหนัง แล้ว Generator เขียนว่า
#
#   "ค้อนหงอนด้ามไฟเบอร์กลาสนี้เหมาะสำหรับงานช่าง... ด้ามไม้ทำให้จับถนัดมือ"
#
# มัน **เอาคำขอของผู้ใช้มาสวมเป็นคุณสมบัติของสินค้า** และขัดกันเองในประโยคเดียว
# (ด้ามไฟเบอร์กลาส vs ด้ามไม้) · ไม่ได้แต่งชื่อหรือราคา จึงรอด `verify_reply()`
# แต่สำหรับระบบแนะนำสินค้าจริงนี่คือการให้ข้อมูลเท็จ
#
# **แก้ด้วยโค้ด ไม่ฝากไว้กับพรอมต์** — บทเรียนขั้น 5.2 บอกว่าโมเดลขนาดนี้ไม่ทำตามกฎ
# ในพรอมต์ → โค้ดขึ้นหัวคำเตือนให้เอง แล้วให้ LLM เขียนต่อ · คำเตือนจึงอยู่แน่นอน 100%
# (เพิ่มกฎในพรอมต์ด้วย แต่ถือเป็นชั้นเสริม ไม่ใช่ชั้นหลัก)
#
# **ทั้ง A1 และ A3 ใช้โหมดนี้** — ตั้งแต่ปรับ A1 ให้ตรงโครง RAG 5 ขั้น (ขั้น 133)
# A1 มี Reranker แล้วจึงรู้ว่าผ่านประตูกี่ชิ้น และส่งธง `weak=` เข้ามาเหมือนกัน
# (เดิม A1 เป็น Naive RAG ไม่มี Reranker จึงใช้โหมดนี้ไม่ได้ — คอมเมนต์เก่าอยู่ตรงนี้)
WEAK_PREFIX_TH = "ไม่พบสินค้าที่ตรงกับที่ขอทั้งหมด แต่มีของใกล้เคียงดังนี้"
WEAK_PREFIX_EN = ("I could not find an exact match for your request. "
                  "Here is the closest I found:")

# เคยลองใส่กฎนี้ในพรอมต์แทนการให้โค้ดเขียนคำตอบ — **ไม่ได้ผล โมเดลเมิน**
# เก็บไว้เป็นหลักฐานว่าลองแล้ว ไม่ได้ใช้งานจริง
WEAK_RULES_UNUSED_TH = """
- สินค้าเหล่านี้อาจไม่ตรงกับที่ผู้ใช้ขอ ห้ามเขียนว่าตรงตามที่ขอ
- บรรยายเฉพาะคุณสมบัติที่อยู่ในข้อมูลที่ให้มา ห้ามเอาคำขอของผู้ใช้มาบรรยายสินค้า"""


@dataclass
class Answer:
    """คำตอบ + ร่องรอยว่าเอาอะไรไปเขียน"""
    reply: str
    language: str
    n_products: int
    context: str = ""            # ข้อเท็จจริงที่ส่งให้โมเดล — ไว้ตรวจย้อน
    llm_calls: int = 0
    unsupported_numbers: list[str] = field(default_factory=list)
    # คำที่เหตุผลปฏิเสธ แต่มีอยู่ในชื่อสินค้า -> ตัวชี้วัดของขั้นที่ 163
    contradicted: list[str] = field(default_factory=list)
    # เหตุผลที่เป็นคำค้นเปล่า ๆ ถูกโค้ดทิ้งไป -> ตัวชี้วัดของขั้นที่ 172
    echoed: list[int] = field(default_factory=list)
    weak: bool = False           # ของตรงไม่ถึงจำนวนที่ต้องการ -> ขึ้นหัวคำเตือนแล้ว

    def trace(self) -> dict:
        # ⚠ ต้องมี `context` — การติดป้าย "คำตอบซื่อตรงไหม" ต้องเทียบคำตอบกับ
        # ข้อเท็จจริงที่ป้อนเข้าไป · รอบแรกลืมใส่ ผลรัน 140 ข้อจึงใช้ติดป้ายไม่ได้
        return {"language": self.language, "n_products": self.n_products,
                "llm_calls": self.llm_calls, "reply_chars": len(self.reply),
                "weak": self.weak, "context": self.context,
                "unsupported_numbers": self.unsupported_numbers,
                "contradicted": self.contradicted,
                "echoed": self.echoed}


def product_facts(hits: list[Hit], language: str = "th") -> str:
    """เรียงข้อเท็จจริงของสินค้าเป็นข้อความให้โมเดลอ่าน

    ส่งแค่สิ่งที่มีในคลังจริง · ตัดรายละเอียดที่ `SNIPPET_CHARS` เพราะ `document`
    คือ `embed_text` ซึ่งยาวได้ถึง 5,000 ตัวอักษร ส่งทั้งก้อน 3 ชิ้นจะช้าและไม่จำเป็น
    (embed_text เรียงจาก ชื่อ → หมวด → แบรนด์ → จุดเด่น → คำบรรยาย ส่วนต้นจึงมีสาระสุด)
    """
    th = language == "th"
    lines = []
    for i, h in enumerate(hits, 1):
        price, stars, store = _fields(h, th)
        detail = " ".join((h.document or "")[:SNIPPET_CHARS].split())
        label = "รายละเอียด" if th else "details"
        lines.append(f"{i}. {h.title}\n"
                     f"   {price} · {stars} · {store} · {h.category}\n"
                     f"   {label}: {detail}")
    return "\n".join(lines)


def _fields(h: Hit, th: bool) -> tuple[str, str, str]:
    """ราคา · คะแนนรีวิว · ร้าน — เขียนจากข้อมูลในคลังล้วน ไม่ผ่าน LLM"""
    price = f"${h.price:,.2f}" if h.price is not None else ("ไม่ระบุราคา" if th
                                                            else "price unknown")
    if h.rating is not None and h.n_reviews:
        stars = (f"{h.rating} ดาว จาก {h.n_reviews:,} รีวิว" if th
                 else f"{h.rating} stars from {h.n_reviews:,} reviews")
    else:
        stars = "ยังไม่มีรีวิว" if th else "no reviews yet"
    return price, stars, h.store or ("ไม่ระบุร้าน" if th else "unknown store")


def assemble(hits: list[Hit], reasons: list[str], language: str = "th") -> str:
    """ประกอบคำตอบด้วยโค้ด — สินค้าครบทุกชิ้นและตัวเลขถูกต้องแน่นอน

    `reasons` ขาดหรือเป็นค่าว่างได้ บรรทัดเหตุผลจะหายไปเฉย ๆ คำตอบไม่พัง
    """
    th = language == "th"
    lines: list[str] = []
    for i, h in enumerate(hits, 1):
        price, stars, store = _fields(h, th)
        why = reasons[i - 1].strip() if i - 1 < len(reasons) else ""
        lines.append(f"{i}. {h.title}")
        lines.append(f"   {price} · {stars} · {store}")
        if why:
            lines.append(f"   {why}")
    return "\n".join(lines)


def _reasons(system: str, user: str, n: int, model: str) -> list[str]:
    """ขอเหตุผลเป็น JSON · **คืนลิสต์ยาว n เสมอ** ขาดเติมค่าว่าง เกินตัดทิ้ง

    ถ้า LLM ล้มหรือตอบ JSON ไม่ได้ คืนค่าว่างทั้งหมด -> คำตอบเหลือแต่ข้อเท็จจริง
    ซึ่งยังใช้ได้ ไม่ใช่ความล้มเหลวของทั้งคำตอบ
    """
    got: list = []
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat", timeout=TIMEOUT,
            json={"model": model, "stream": False, "format": "json",
                  "options": {"temperature": TEMPERATURE, "seed": 0},
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}]})
        response.raise_for_status()
        data = json.loads(response.json()["message"]["content"])
        raw = data.get("reasons")
        got = raw if isinstance(raw, list) else []
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
        got = []
    out = [str(x).strip() if isinstance(x, (str, int, float)) else ""
           for x in got[:n]]
    return out + [""] * (n - len(out))


# ⚠ **ตัวตรวจคำที่ขัดกับชื่อสินค้า** — เพิ่มเมื่อขั้นที่ 163
#
# วัดรูปแบบความผิดพลาดที่ป้าย ข รอบใหม่เจอ คือเหตุผล**ปฏิเสธ**คุณสมบัติที่
# **ชื่อสินค้าที่ป้อนให้บอกไว้เอง** · ใช้เป็นตัวชี้วัด ไม่ได้ใช้ตัดเหตุผลทิ้ง
# เพราะยังมีโอกาสตั้งธงผิด (เช่นชื่อมีคำว่า Non-Stick แล้วเหตุผลเขียน does not stick)
#
# ⚠ **ตรวจได้เฉพาะฝั่งอังกฤษ** เพราะภาษาไทยไม่เว้นวรรค ตัดคำไม่ได้ด้วย regex
# ฝั่งไทยรูปแบบความผิดพลาดเป็นอีกแบบ คือลอกคำค้นของผู้ใช้มาวางเป็นเหตุผล
_NEGATION = re.compile(
    # ⚠ ต้องมีขอบคำ ไม่งั้น `lacks?` จะจับคำว่า B-lack เป็นการปฏิเสธ (เจอ 2026-10-13)
    # (เจอตอนตรวจผลรอบ 2026-10-13 · ทำให้นับเกินทั้งสองรอบ)
    r"\b(?:does\s+not|doesn't|do\s+not|don't|is\s+not|isn't|are\s+not|aren't|lacks?)\b\s+"
    r"(?:have|has|mention|specify|state|include|match|appear)?\s*([^.;,]{0,70})",
    re.IGNORECASE)

# คำกลางที่โผล่ในชื่อสินค้าได้โดยไม่ใช่คุณสมบัติ -> ไม่นับเป็นการขัดกัน
_NEUTRAL = {"the", "a", "an", "and", "or", "of", "for", "with", "to", "in", "on",
            "be", "being", "user", "users", "request", "requested", "product",
            "item", "items", "this", "that", "it", "its", "as", "by", "from",
            "not", "does", "have", "has", "mention", "mentioned", "specify",
            "specified", "match", "matches", "matching", "feature", "features",
            "specific", "specifically", "what", "asked", "looking", "size"}


def contradicted_terms(reason: str, title: str) -> list[str]:
    """คำที่เหตุผล**ปฏิเสธ** แต่**มีอยู่ในชื่อสินค้า**ที่ป้อนให้

        >>> contradicted_terms("it doesn't mention being squeaky",
        ...                    "Large Dog Squeaky Plush Toys")
        ['squeaky']
        >>> contradicted_terms("it's not specifically for large dogs",
        ...                    "Spiky Squeaky Balls for All Dogs")
        []
    """
    have = set(re.findall(r"[a-z]+", title.lower()))
    out: list[str] = []
    for clause in _NEGATION.findall(reason):
        for w in re.findall(r"[a-z]+", clause.lower()):
            if len(w) >= 4 and w not in _NEUTRAL and w in have and w not in out:
                out.append(w)
    return out


# -------------------------------------------------------------------------
# ⚠ **โค้ดจับ 'เหตุผลที่เป็นคำค้นเปล่า ๆ' แล้วทิ้ง — เพิ่มเมื่อขั้นที่ 172**
#
# วัดจากผลรันรอบที่ 3 ทั้งสองภาษา: ฝั่งไทย **33/258 คำตอบ** เขียนประโยค
# เดียวกันซ้ำหลายชิ้น ฝั่งอังกฤษ **0/259** · และ **99/99 บรรทัดที่ซ้ำกัน
# เป็นคำค้นเปล่าทั้งหมด** จึงเป็นอาการเดียวไม่ใช่สองอาการ ใช้กฎข้อเดียวครอบได้
#
# ไม่สัมพันธ์กับความตรงของสินค้า (มีชิ้นตรงเป๊ะ 10.3% vs ไม่มีเลย 14.0%)
# และ **ลองใหม่ไม่ช่วย** เพราะ TEMPERATURE = 0 ถอดรหัสแบบ greedy ผลเท่าเดิมทุกครั้ง
#
# กฎที่ใช้คือ **เท่ากับคำค้นเป๊ะ** หลังตัดช่องว่าง ไม่ใช่ค่าขอบที่ตั้งเอง
# เพราะวัดได้ว่าบรรทัดที่เข้าข่ายทั้ง **111 บรรทัดเติมเกินคำค้น 0 ตัวอักษรพอดี**
# -> ไม่มีผลบวกลวงโดยนิยาม · ส่วนการแปลที่ถูกต้องซึ่งมีคำค้นอยู่ด้วยเติม 1-88 ตัว
#
# ใช้กับ**ทั้งสองภาษาเท่ากัน** เพื่อไม่ให้ฝั่งไทยได้เกราะที่ฝั่งอังกฤษไม่มี
# (ฝั่งอังกฤษไม่เคยเข้าข่าย การเทียบจึงไม่เสีย)
#
# ทิ้งแล้วคำตอบเหลือข้อเท็จจริงล้วน ซึ่งเป็นสภาพที่ `_reasons` รับไว้อยู่แล้ว
# ตอน LLM ล้ม · บรรทัดที่ถูกทิ้งบันทึกไว้ที่ `Answer.echoed` เพื่อรายงานได้ทั้ง
# พฤติกรรมดิบของโมเดลและผลหลังกรอง จากการรันครั้งเดียว
# -------------------------------------------------------------------------
def echoes_query(reason: str, question: str) -> bool:
    """เหตุผลนี้เป็น**คำค้นเปล่า ๆ** ไม่ได้เติมข้อมูลจากคลังเลยหรือไม่

        >>> echoes_query("กางเกงวอร์มสีส้มผู้ชาย", "กางเกงวอร์มสีส้มผู้ชาย")
        True
        >>> echoes_query("กางเกงวอร์ม สีส้ม ผู้ชาย", "กางเกงวอร์มสีส้มผู้ชาย")
        True
        >>> echoes_query("กางเกงวอร์มสีส้มผู้ชาย ผ้าโพลีเอสเตอร์ รีดได้",
        ...              "กางเกงวอร์มสีส้มผู้ชาย")
        False
        >>> echoes_query("", "กางเกงวอร์มสีส้มผู้ชาย")
        False
    """
    q = re.sub(r"\s+", "", question.lower())
    return bool(q) and re.sub(r"\s+", "", reason.lower()) == q


_NUMBER = re.compile(r"\d[\d,]*\.?\d*")


def _norm_num(raw: str) -> str:
    """ตัดจุดท้ายประโยคและศูนย์ท้ายทิ้ง — "12." กับ "12" คือเลขเดียวกัน"""
    s = raw.rstrip(".")
    return s.rstrip("0").rstrip(".") if "." in s else s


def verify_reply(reply: str, context: str, question: str = "") -> list[str]:
    """หาตัวเลขในคำตอบที่ไม่มีหลักฐานรองรับ

    ไม่ใช่การตรวจจับการแต่งข้อมูลแบบสมบูรณ์ — เป็นสัญญาณเตือนที่ถูกและเร็ว
    ตัวเลข 1-5 ถูกข้ามเพราะเป็นเลขข้อในลิสต์

    ⚠ **ต้องนับตัวเลขในคำถามของผู้ใช้เป็นหลักฐานด้วย** ไม่ใช่แค่ข้อเท็จจริงของสินค้า
    วัดครั้งแรกไม่ได้ส่ง `question` เข้ามา ทำให้ตั้งธงผิด 17/84 ข้อ เช่น
        ถาม "garmin dash cam mini under $12"
        ตอบ "The price is under $12, but it does not mention being a dash cam"
    เลข 12 มาจากปากผู้ใช้เอง การทวนกลับไม่ใช่การแต่งข้อมูล
    (ส่วนคำถามว่าของ**ถูกกว่างบจริงไหม** วัดแยกด้วยอัตราละเมิดงบ)
    """
    have = {_norm_num(x) for x in
            _NUMBER.findall((context + " " + question).replace(",", ""))}
    out = []
    for raw in _NUMBER.findall(reply.replace(",", "")):
        if raw in ("1", "2", "3", "4", "5"):
            continue
        if _norm_num(raw) not in have:
            out.append(raw)
    return out


def _chat(system: str, user: str, model: str = CHAT_MODEL) -> str:
    response = httpx.post(
        f"{OLLAMA_URL}/api/chat", timeout=TIMEOUT,
        json={"model": model, "stream": False,
              "options": {"temperature": TEMPERATURE, "seed": 0},
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]})
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def generate(question: str, hits: list[Hit], language: str = "th",
             weak: bool = False, model: str = CHAT_MODEL) -> Answer:
    """เขียนคำตอบจากสินค้าที่ค้นได้

        >>> hits, plan = translate.search(retriever, "เสื่อโยคะกันลื่น", k=5)
        >>> ans = generate("เสื่อโยคะกันลื่น", hits, plan.language)
        >>> print(ans.reply)

    ถ้าไม่มีสินค้าเลย คืนข้อความคงที่ **ไม่เรียก LLM** — ไม่มีอะไรให้เขียน
    และปล่อยให้โมเดลเขียนเองตอนไม่มีข้อมูลคือการเปิดช่องให้มันแต่งสินค้าขึ้นมา
    """
    th = language == "th"
    if not hits:
        return Answer(reply=EMPTY_TH if th else EMPTY_EN, language=language,
                      n_products=0, llm_calls=0)

    context = product_facts(hits, language)
    if th:
        user = (f'ผู้ใช้ขอ: "{question}"\n\nสินค้าที่ระบบเลือกมา:\n{context}\n\n'
                f"เขียนเหตุผลให้ครบ {len(hits)} ชิ้น")
    else:
        user = (f'User asked: "{question}"\n\nProducts the system picked:\n{context}\n\n'
                f"Write one reason for each of the {len(hits)} products")

    if weak:
        # ⚠ **โหมดอ่อนไม่เรียก LLM เลย** — โค้ดเขียนคำตอบทั้งก้อน
        #
        # ลองใส่กฎในพรอมต์ก่อนแล้ว **ไม่ได้ผล** — โมเดลยังเขียนว่า
        # "ค้อนหงอนด้ามไฟเบอร์กลาสสำหรับงานช่างที่ทำจากวัสดุไนลอน..." ให้ค้อนหนัง
        # ทั้งที่พรอมต์ห้ามไว้ชัด (หลักฐานชิ้นที่ 6 ว่าโมเดลไม่ทำตามกฎในพรอมต์)
        #
        # เหตุผลเชิงออกแบบ: **งานของ LLM คือเขียนว่าสินค้าตรงกับที่ขอเพราะอะไร
        # ซึ่งเป็นงานที่ไม่มีคำตอบที่ถูกเมื่อสินค้าไม่ตรง** → ไม่ควรให้มันทำ
        # โค้ดลิสต์ข้อเท็จจริงให้ผู้ใช้ตัดสินเอง ปลอดภัย 100% และประหยัด 1 LLM
        prefix = WEAK_PREFIX_TH if th else WEAK_PREFIX_EN
        return Answer(reply=f"{prefix}\n\n{context}", language=language,
                      n_products=len(hits), context=context,
                      llm_calls=0, weak=True)

    reasons = _reasons(REASON_SYSTEM_TH if th else REASON_SYSTEM_EN,
                       user, len(hits), model)

    # ทิ้งเหตุผลที่เป็นคำค้นเปล่า ๆ **ก่อน** ประกอบคำตอบ (เหตุผลในคอมเมนต์ข้างบน)
    echoed = [i for i, why in enumerate(reasons, 1)
              if echoes_query(why, question)]
    for i in echoed:
        reasons[i - 1] = ""

    reply = assemble(hits, reasons, language)

    # นับการขัดกับชื่อสินค้า ทีละชิ้น -> เหตุผลชิ้นไหนขัด ก็รู้ว่าชิ้นไหน
    bad: list[str] = []
    for h, why in zip(hits, reasons):
        for w in contradicted_terms(why, h.title):
            if w not in bad:
                bad.append(w)

    return Answer(reply=reply, language=language, n_products=len(hits),
                  context=context, llm_calls=1, weak=weak,
                  unsupported_numbers=verify_reply(reply, context, question),
                  contradicted=bad, echoed=echoed)


# ---------------------------------------------------------------------------
# คำตอบอีก 2 แบบที่ Planner เลือกได้ — **A3 ใช้ · A1 ไม่ใช้เพราะไม่มี Planner**
# ---------------------------------------------------------------------------

ASK_SYSTEM_TH = """คุณคือผู้ช่วยแนะนำสินค้า ข้อมูลยังไม่พอจะแนะนำ

ถามกลับ **คำถามเดียว** สั้น ๆ เพื่อถามสิ่งที่ยังไม่รู้ (หมวดสินค้า งบ การใช้งาน หรือคุณสมบัติ)
อย่าถามสิ่งที่ผู้ใช้บอกมาแล้ว · อย่าแนะนำสินค้าในรอบนี้"""

ASK_SYSTEM_EN = """You are a product recommendation assistant. You do not have enough
information yet.

Ask exactly ONE short follow-up question about what is still unknown (category,
budget, use case, or features). Do not ask what the user already told you.
Do not recommend any product this turn."""

CHAT_SYSTEM_TH = """คุณคือผู้ช่วยแนะนำสินค้า ผู้ใช้ยังไม่ได้ขอสินค้า
ตอบสั้น ๆ สุภาพ แล้วชวนให้บอกว่าอยากได้สินค้าแบบไหน"""

CHAT_SYSTEM_EN = """You are a product recommendation assistant. The user is not asking
for a product yet. Reply briefly and politely, then invite them to say what they want."""


def generate_question(profile: dict, user_message: str, language: str = "th",
                      model: str = CHAT_MODEL) -> Answer:
    """เขียนคำถามกลับ — ใช้เมื่อ Planner เลือก `ask`

    ส่งโปรไฟล์ไปด้วยเพื่อไม่ให้ถามซ้ำสิ่งที่ผู้ใช้บอกมาแล้ว
    """
    th = language == "th"
    import json as _json
    known = _json.dumps(profile, ensure_ascii=False)
    user = (f'สิ่งที่รู้แล้ว: {known}\nข้อความล่าสุด: "{user_message}"\nถามกลับหนึ่งคำถาม'
            if th else
            f'Known so far: {known}\nLatest message: "{user_message}"\nAsk one question')
    reply = _chat(ASK_SYSTEM_TH if th else ASK_SYSTEM_EN, user, model)
    return Answer(reply=reply, language=language, n_products=0, llm_calls=1)


def generate_chat(user_message: str, language: str = "th",
                  model: str = CHAT_MODEL) -> Answer:
    """ตอบคุยทั่วไป — ใช้เมื่อ Planner เลือก `chat`"""
    th = language == "th"
    reply = _chat(CHAT_SYSTEM_TH if th else CHAT_SYSTEM_EN, user_message, model)
    return Answer(reply=reply, language=language, n_products=0, llm_calls=1)
