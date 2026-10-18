"""ให้ agent บอกว่า **ข้อกำหนดข้อไหนที่ผลลัพธ์ยังไม่ตอบ** — ขั้นที่ 2 ทาง ข

# ⚠⚠⚠ ทดลองแล้วไม่ผ่าน — ปิดอยู่ อย่าเปิดโดยไม่อ่านก่อน (16 ต.ค. 2026)

`src/a3.py` ตั้ง `USE_CRITIQUE = False` **เก็บไฟล์นี้ไว้ไม่ลบ** เพราะตัวเลข
ข้างล่างต้องทำซ้ำได้เพื่ออ้างในเล่ม · วัด end-to-end ฝั่งอังกฤษ 140 คำค้น × 3 แขน

| กลุ่ม | ก่อนเปิด ข | เปิด ข |
|---|---|---|
| คลังมีของ | A3C = A1 **เป๊ะทุกทศนิยม** 0.5594 | A3C 0.5866 เทียบ A1 0.5995 **-1.3 จุด** |
| มีงบจำกัด | A3C = A1 **เป๊ะทุกทศนิยม** 0.5096 | A3C 0.5189 เทียบ A1 0.5497 **-3.1 จุด** |
| คลังไม่มีของ | A3C 0.0732 ชนะ A1 | ไม่กระทบ (`picked` ว่าง โค้ดข้าม action นี้) |

**สาเหตุ** โมเดล 8B เลือกว่า "คำไหนเป็นข้อกำหนด" ไม่แม่น — ทิ้งคำที่ควรเก็บ
(`gowdy` = แบรนด์ ซึ่งพรอมต์สั่งให้เก็บไว้ชัด ๆ) และเก็บคำที่ไม่ใช่ข้อกำหนด
→ ถ่วงผิดคำ ของดีหลุดจาก 3 อันดับแรก · **ซ้ำรอย κ 0.08-0.25 ของ LLM-as-judge
ที่ mark5 วัดไว้** และเป็นหลักฐานชิ้นที่สามว่าโมเดลขนาดนี้ตัดสินความตรงไม่ได้

🔑 **สิ่งที่ยังใช้ได้จากไฟล์นี้** ฝั่งโค้ด (`_candidate_terms`) หาคำที่ขาดได้
**73-83% ของคำค้น** แม่นกว่าฝั่ง LLM — ถ้าจะลองต่อ ควรใช้โค้ดล้วนไม่ผ่าน LLM
แต่ค่าที่วัดบนกองจำกัดก็ยังเป็นลบ (-0.3 ถึง -0.6) จึงไม่ได้ทำต่อ

---


**ทำไมต้องมี** ตรวจสายพานทั้งเส้นแล้วพบว่าของดี (ป้าย >= 2) ตายที่ชั้นจัดอันดับ
48% มากกว่าทุกชั้นอื่นรวมกัน 8 เท่า · และถ้าเรียงของในกองได้ถูกเป๊ะจะได้
ไทย 0.5858 -> 0.7000 · อังกฤษ 0.5967 -> 0.6709 → **ของดีอยู่ในกองแล้ว แค่เรียงไม่ขึ้น**

**ทำไมปรับน้ำหนักไม่พอ** (docs/steps.md ข้อ 288-289) ดันน้ำหนักคำซ้อนขึ้นเป็น
20 · 40 · 100 ได้ลำดับ**เท่ากันเป๊ะ** เพราะ RRF ใช้แค่อันดับ ไม่ใช้ค่าดิบ
พอสัญญาณหนึ่งครองการเรียงแล้ว เพิ่มอีกก็ไม่เปลี่ยน
→ ตัวจัดอันดับ **ขาดสัญญาณ ไม่ได้ขาดการปรับน้ำหนัก**

**สัญญาณที่โค้ดคำนวณเองไม่ได้** คือ "ในบรรดาคำที่ผู้ใช้พูด คำไหนเป็น**ข้อกำหนด
ที่ขาดไม่ได้**" — `word_overlap` ให้น้ำหนักทุกคำเท่ากัน ทั้งที่ `2tb` กับ
`freestanding` ชี้ขาดความตรง ส่วน `drive` กับ `desk` เป็นเพียงชนิดสินค้า

## 🔑 ต่างจากสิ่งที่เคยทำแล้วไม่ผ่านอย่างไร

`rewrite.py` มีคำเตือนว่าการส่งชื่อสินค้าที่ค้นมาได้เข้าไปในพรอมต์ **ล้มเหลว**
(ข้อ 238-239) เพราะเป็น self-refine — โมเดลยอมแพ้หรือไขว้เขว
(`serta kleinmon` + ชื่อสินค้าผิด -> `calvin klein men's t-shirt`)

ไฟล์นี้ส่งชื่อสินค้าเข้าไปเหมือนกัน **แต่โหมดของงานต่างกันคนละแบบ**

| | `rewrite` (ไม่ผ่าน) | ไฟล์นี้ |
|---|---|---|
| ขอให้โมเดลทำอะไร | **แต่ง**คำค้นใหม่ | **เลือก**จากรายการที่โค้ดทำให้ |
| พื้นที่คำตอบ | เปิด — คำอะไรก็ได้ | **ปิด** — เลือกได้แค่จากรายการ |
| ไขว้เขวได้ไหม | ได้ และเกิดขึ้นจริง | **ไม่ได้ โค้ดทิ้งทุกคำที่ไม่อยู่ในรายการ** |
| ยอมแพ้แล้วเป็นไง | ลูปหยุด ตอบว่าไม่พบ | **ไม่ทำอะไร ผลเท่าเดิม** |

ความล้มเหลวแบบ ก (ไขว้เขว) จึง **ถูกปิดด้วยโค้ด ไม่ได้ฝากไว้กับพรอมต์**
และความล้มเหลวอีกแบบ (ยอมแพ้) ตกไปที่ "ไม่ทำอะไร" ซึ่งปลอดภัย

**แบ่งงานตามที่ขั้น 5.6 วัดไว้**

| งาน | ใครทำ | หลักฐาน |
|---|---|---|
| หาว่าคำไหน*ขาด*จากชื่อสินค้า | **โค้ด** (งานนับ) | κ 0.824 ต่อ 0.000 |
| เลือกว่าคำไหน*เป็นข้อกำหนด* | **LLM** (งานภาษา) | κ 0.646 ต่อ 0.280 |

⚠ ต้องสตาร์ต Ollama ก่อน:  ollama.exe serve
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed import OLLAMA_URL                                     # noqa: E402
from rerank import present                                       # noqa: E402
from translate import CHAT_MODEL                                 # noqa: E402

TIMEOUT = 180
MAX_TERMS = 3          # เลือกมากกว่านี้ = สัญญาณเจือจาง กลายเป็น word_overlap เดิม

# คำที่ไม่เคยเป็นข้อกำหนด — ถึงโมเดลเลือกมาก็ทิ้ง
STOPWORDS = frozenset(
    "the a an for with and of to in on at set pack size under over cheap "
    "best good new buy want need please product item thing".split())

CRITIQUE_SYSTEM = """A shopper asked for something. A search returned products.
Some words from the request do not appear in the product titles.

From the list of missing words, pick the ones that are REAL REQUIREMENTS —
a capacity, size, material, colour, brand or special feature the shopper insists on.

Leave out words that merely name the product type (desk, drive, hammer, ball)
and words that do not change whether a product is right.

Pick only from the list given. Answer with those words separated by commas
on one line, or NONE if none of them is a real requirement. No explanation."""


def _candidate_terms(search_text: str, titles: list[str]) -> list[str]:
    """คำในคำค้นที่ **ขาดจากชื่อสินค้าส่วนใหญ่** — โค้ดหาเองได้ ไม่ต้องใช้ LLM

    เชื่อมเลขกับหน่วยเข้าด้วยกันด้วย เพราะคลังเขียนติดกัน ("2 tb" -> ลอง "2tb")
    เทียบแบบ substring ไม่ใช่ทั้งคำ เพราะ "tb" ซ่อนอยู่ใน "1TB"

        >>> _candidate_terms("2 tb usb flash drive", ["1TB USB Flash Drive"])
        ['2', '2tb']
    """
    toks = re.findall(r"[a-z0-9]+", search_text.lower())
    terms = list(toks)
    for a, b in zip(toks, toks[1:]):
        if a.isdigit() and b.isalpha() and len(b) <= 3:
            terms.append(a + b)
    low = [t.lower() for t in titles]
    out = []
    for t in dict.fromkeys(terms):
        if t in STOPWORDS or len(t) < 2:
            continue
        # ขาดจากชื่อสินค้า**ส่วนใหญ่** (ไม่ใช่ทุกชิ้น) จึงยังเป็นสัญญาณให้จัดอันดับได้
        if sum(1 for s in low if present(t, s)) * 2 < len(low):
            out.append(t)
    return out


def missing_terms(search_text: str, titles: list[str],
                  model: str = CHAT_MODEL) -> list[str]:
    """คืนคำที่เป็น **ข้อกำหนดที่ผลลัพธ์ยังไม่ตอบ** · คืน `[]` = ไม่ทำอะไร

    `search_text` คำค้นภาษาอังกฤษที่ใช้ค้นจริง (คำของผู้ใช้ หรือคำแปลรอบแรก)
    `titles`      ชื่อสินค้าที่กำลังจะตอบ

    **โค้ดบังคับ ไม่ฝากไว้กับพรอมต์:** โมเดลเลือกได้เฉพาะจาก**รายการปิด**ที่โค้ด
    ส่งให้ คำที่ไม่อยู่ในรายการถูกทิ้งทั้งหมด → **ไขว้เขวไม่ได้เลย**
    และถ้าโมเดลตอบ NONE หรือตอบผิดรูป ผลคือ "ไม่ทำอะไร" ซึ่งปลอดภัย

    ไม่มีอะไรขาด -> **ไม่เรียก LLM เลย** ประหยัดเวลาในกรณีที่พบบ่อยที่สุด
    """
    cands = _candidate_terms(search_text, titles)
    if not cands:
        return []

    lines = [f"  - {t[:110]}" for t in titles]
    user = ("\n".join([f'Request: "{search_text}"', "Products returned:", *lines,
                       "Missing words: " + ", ".join(cands),
                       "Which of these missing words are real requirements?"]))
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat", timeout=TIMEOUT,
            json={"model": model, "stream": False,
                  "options": {"temperature": 0, "seed": 0},
                  "messages": [{"role": "system", "content": CRITIQUE_SYSTEM},
                               {"role": "user", "content": user}]})
        response.raise_for_status()
        raw = response.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError):
        return []                        # ต่อไม่ได้ -> ไม่ทำอะไร ผลเท่าเดิม

    head = raw.strip().splitlines()[0] if raw.strip() else ""
    if not head or head.strip().upper().startswith("NONE"):
        return []

    low = head.lower()
    # เลือกได้เฉพาะจากรายการปิด · เรียงตามลำดับในรายการ ไม่ตามลำดับที่โมเดลตอบ
    return [c for c in cands if c in low][:MAX_TERMS]


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    for q, ts in (("2 tb usb flash drive",
                   ["1TB USB Flash Drive High Speed Metal Memory Stick",
                    "USB Drive 1TB with Keychain Portable Thumb Drive",
                    "256GB Flash Drive Type C 2-in-1 USB 3.0"]),
                  ("gowdy height adjustable standing desk",
                   ["Marsail Standing Desk Adjustable Height, Electric",
                    "GOFLAME Height Adjustable Electric Standing Desk",
                    "Giantex Electric Standing Desk 44 x 24 Inch"]),
                  ("squeaky balls for large dogs",
                   ["Squeaky Balls for Large Dogs 4 Pack Durable",
                    "Dog Squeaky Ball Toys for Large Breed Aggressive",
                    "Large Dog Squeaky Balls Rubber Fetch Toy"])):
        print(f"{q!r}")
        print(f"   โค้ดหาคำที่ขาด -> {_candidate_terms(q, ts)}")
        print(f"   LLM เลือก      -> {missing_terms(q, ts)}")
