"""ฟังก์ชันสร้าง feature — ล้วน ๆ ไม่แตะไฟล์ ไม่แตะ DataFrame

แยกออกมาเพื่อให้ทดสอบได้ง่ายและอ่านเข้าใจได้โดยไม่ต้องมีข้อมูลจริง
ตัวที่เรียกใช้คือ `build_feature.py`
"""

from __future__ import annotations

# --------------------------------------------------------------------------- ตัวเลข


def to_number(value) -> float | None:
    """คืน float หรือ None — กัน NaN หลุดเข้าสูตรคำนวณ

    ⚠ `value or 0` ใช้กับ NaN ไม่ได้ เพราะ **NaN เป็น truthy ใน Python**
    (`float("nan") or 0` คืน nan ไม่ใช่ 0) ถ้าไม่ดักตรงนี้ NaN จะไหลทะลุสูตรไปเงียบ ๆ
    แล้วโผล่เป็นค่าว่างในคอลัมน์ที่ควรมีค่าครบทุกแถว
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number      # x != x เป็นจริงเฉพาะกับ NaN


def popularity(rating, rating_count, mean_rating: float, m: float) -> float:
    """คะแนนความนิยมแบบ Bayesian (สูตรเดียวกับที่ IMDb ใช้)

        popularity = v/(v+m) × R  +  m/(v+m) × C

    `v` จำนวนรีวิวของสินค้านี้ · `R` คะแนนของสินค้านี้
    `m` เกณฑ์จำนวนรีวิวขั้นต่ำ · `C` คะแนนเฉลี่ยของทั้งคลัง

    **ปัญหาที่แก้:** 12.3% ของสินค้ามีรีวิวแค่ครั้งเดียว ถ้าเรียงตามคะแนนดิบ
    สินค้า 5 ดาวจากรีวิวเดียวจะชนะสินค้า 4.5 ดาวจากพันรีวิว ทั้งที่เชื่อถือได้น้อยกว่ามาก
    สูตรนี้ดึงสินค้าที่รีวิวน้อยเข้าหาค่าเฉลี่ยรวม ยิ่งรีวิวเยอะยิ่งเชื่อคะแนนตัวเอง
    """
    v = to_number(rating_count) or 0.0
    R = to_number(rating)
    R = mean_rating if R is None else R
    if v + m == 0:
        return round(mean_rating, 4)
    return round(v / (v + m) * R + m / (v + m) * mean_rating, 4)


def value_score(rating, price) -> float | None:
    """ความคุ้มค่า = คะแนนรีวิว ÷ ราคา

    ปัดที่ 6 ตำแหน่ง **ไม่ใช่ 4** เพราะสินค้าราคาสูงสุดในคลัง ($49,484) ให้ค่าราว 1e-5
    ถ้าปัด 4 ตำแหน่งจะกลายเป็น 0.0 เหมือนกันหมด สินค้าคนละตัวได้คะแนนเท่ากัน
    เสียสัญญาณที่ใช้จัดอันดับ (บทเรียนจากโปรเจกต์รุ่นก่อน)
    """
    r = to_number(rating)
    p = to_number(price)
    if r is None or p is None or p <= 0:
        return None
    return round(r / p, 6)


# --------------------------------------------------------------------------- ข้อความ

# key ที่ **ไม่** ใส่ใน embed_text เพราะเป็นรหัสหรือวันที่ ไม่มีความหมายเชิงค้นหา
# ค่าของมันเป็นสตริงสุ่ม (เช่น "B0BX6RRTZD", "AB-1234-X") ใส่ไปมีแต่ทำให้เวกเตอร์เพี้ยน
# ผู้ใช้ไม่มีทางค้นหาด้วย "สินค้าที่มีรหัสรุ่น AB-1234-X"
SKIP_DETAIL_KEYS = {
    "Date First Available", "Item model number", "Manufacturer Part Number",
    "Part Number", "ASIN", "UPC", "UPC EAN Code", "Global Trade Identification Number",
    "Batteries", "Customer Reviews", "Best Sellers Rank",
}

# ค่ายาวเกินนี้มักเป็นข้อความโฆษณาที่หลุดมาอยู่ในช่องสเปก ไม่ใช่สเปกจริง
MAX_VALUE_LEN = 120


def details_to_text(details: dict) -> str:
    """แปลง `details_json` ทั้งก้อนเป็นข้อความ

    **ใส่ทุก key ที่สินค้าชิ้นนั้นมี** — แต่ละชิ้นมีไม่เท่ากัน (มัธยฐาน 7, มากสุด 51)
    ซึ่งเป็นเรื่องปกติของข้อมูลแบบ schema-less และไม่ใช่ปัญหาสำหรับการค้นหาด้วยความหมาย

    ตัดออกเฉพาะ: รหัส/วันที่ (ดู `SKIP_DETAIL_KEYS`) · ค่าที่เป็น dict/list ซ้อน ·
    ค่าว่าง · ค่าที่ยาวผิดปกติ
    """
    parts = []
    for key, value in details.items():
        if not key or key in SKIP_DETAIL_KEYS:
            continue
        if isinstance(value, (dict, list, tuple)):
            continue
        text = str(value).strip()
        if not text or len(text) > MAX_VALUE_LEN:
            continue
        parts.append(f"{key}: {text}")
    return " | ".join(parts)


def build_embed_text(title, category, store, features, description,
                     details: dict, max_chars: int | None = None) -> str:
    """ข้อความก้อนเดียวที่จะถูกแปลงเป็นเวกเตอร์ในขั้นที่ 4

    เรียงจากสำคัญมากไปน้อย: ชื่อ → หมวด → แบรนด์ → จุดเด่น → คำอธิบาย → สเปก
    ที่เรียงแบบนี้เพราะถ้าโดนตัดที่ `max_chars` ส่วนที่หายจะเป็นส่วนที่สำคัญน้อยที่สุด
    และ `title` เป็นแหล่งเดียวที่ไม่หายเลยสักแถว จึงต้องอยู่หน้าสุดเสมอ
    """
    parts: list[str] = []

    if title and str(title).strip():
        parts.append(str(title).strip())
    if category and str(category).strip():
        parts.append(f"Category: {str(category).strip()}")
    if store and str(store).strip():
        parts.append(f"Brand: {str(store).strip()}")

    if features is not None:
        parts.extend(str(f).strip() for f in features if str(f).strip())

    if description and str(description).strip():
        parts.append(str(description).strip())

    tail = details_to_text(details)
    if tail:
        parts.append(tail)

    text = " | ".join(parts)
    return text[:max_chars] if max_chars else text
