"""ขั้นที่ 2 — ล้างข้อมูล

จากข้อมูลดิบ 117,243 แถว × 16 คอลัมน์ → ข้อมูลสะอาดที่พร้อมเอาไปสร้าง feature

ทำตามการตัดสินใจใน `docs/data_plan.md`:
  ข้อ 1  ใช้ครบทุกหมวด ไม่ตัดหมวดใดทิ้ง
  ข้อ 2  `category` มาจาก `filename` (หาย 0%) · เก็บ `categories` ไว้เป็นหมวดย่อย
  ข้อ 3  ตัดแถวที่ไม่มีราคาทิ้ง → เหลือ ~81,264 แถว

รัน:  python src\\clean.py
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import pyarrow.ipc as ipc

from text_clean import clean_text, clean_text_list

sys.path.insert(0, str(Path(__file__).resolve().parent))   # ให้ import text_clean ได้ทั้งตอนรันตรงและตอน import

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "products_raw.feather"
CLEAN_FILE = ROOT / "data" / "clean" / "products_clean.feather"

# คอลัมน์ที่ไม่อ่านเข้ามาเลย
#   embeddings        เวกเตอร์ OpenAI 1,536 มิติ — กิน 91% ของไฟล์ และใช้ค้นต้องจ่ายเงินเรียก API
#   __index_level_0__ เลขลำดับที่ติดมาตอนแปลงไฟล์ ไม่ใช่ข้อมูลจริง
#   main_category     หาย 21.2% และค่าปนกันเอง (AMAZON FASHION กับ Amazon Fashion)
#                     — เลือกใช้ `filename` แทนแล้ว เก็บไว้ทั้งคู่จะทำให้สับสนว่าควรกรองด้วยอันไหน
#   date_first_available  แทบไม่มีความต่าง: ปี 2023 มี 81,249 แถว ปี 2024 มีแค่ 15 แถว
#                     ใช้แยกแยะอะไรไม่ได้ และทำ "สินค้าใหม่ล่าสุด" ก็ไม่ได้เพราะทุกชิ้นปีเดียวกัน
#
# ส่วน `filename` อ่านเข้ามาเพื่อสร้าง `category` แล้วตัดทิ้งทีหลัง (ดูท้ายฟังก์ชัน clean)
# เพราะทั้งสองจับคู่กัน 1:1 เป๊ะ (29 ↔ 29 ค่า) เก็บไว้ทั้งคู่จะสับสนว่าควรกรองด้วยอันไหน
#
# ทุกคอลัมน์ยังอยู่ครบในไฟล์ raw ถ้าวันหนึ่งต้องการกลับมาใช้
DROP_COLUMNS = {"embeddings", "__index_level_0__", "main_category", "date_first_available"}

HTML_TAG = re.compile(r"<[^>]{1,40}>")
NON_ASCII = re.compile(r"[^\x00-\x7f]")


def read_raw() -> pd.DataFrame:
    """อ่านข้อมูลดิบ โดยไม่โหลดคอลัมน์ที่ไม่ใช้เข้าหน่วยความจำเลย"""
    with open(RAW_FILE, "rb") as f:
        names = ipc.open_file(f).schema.names
    columns = [c for c in names if c not in DROP_COLUMNS]
    return pd.read_feather(RAW_FILE, columns=columns)


def category_from_filename(value) -> str | None:
    """`meta_Home_and_Kitchen` -> `Home and Kitchen`

    `filename` คือชื่อไฟล์ต้นทางของ Amazon ซึ่งก็คือหมวดระดับบนสุด
    วัดแล้วไม่หายเลยสักแถวและมีแค่ 30 ค่า จึงเป็นแหล่งหมวดที่ดีที่สุดในข้อมูลชุดนี้
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return value.removeprefix("meta_").replace("_", " ").strip() or None


def parse_details(raw) -> dict:
    """แปลง `details` จากข้อความเป็น dict — ทนต่อค่าที่แปลงไม่ได้ ไม่โยน exception

    ใช้ `ast.literal_eval` ไม่ใช่ `json.loads` เพราะต้นทางเป็น repr ของ dict ใน Python
    (ใช้ single quote) ไม่ใช่ JSON จริง · วัดแล้วแปลงสำเร็จ 100%
    """
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def strip_html(text) -> str:
    if not isinstance(text, str):
        return ""
    return HTML_TAG.sub(" ", text).strip()


def check(condition: bool, message: str) -> None:
    """ด่านตรวจคุณภาพ — ไม่ผ่านคือหยุด ไม่ปล่อยข้อมูลเสียไหลลงขั้นถัดไป"""
    if not condition:
        raise SystemExit(f"❌ ไม่ผ่านการตรวจ: {message}")


def clean() -> pd.DataFrame:
    started = time.perf_counter()
    print("อ่านข้อมูลดิบ ...")
    df = read_raw()
    before = len(df)
    print(f"  {before:,} แถว × {df.shape[1]} คอลัมน์ (ไม่อ่าน {', '.join(sorted(DROP_COLUMNS))})")

    # --- หมวดสินค้า: มาจาก filename ---
    df["category"] = df["filename"].map(category_from_filename)
    n_cat_missing = int(df["category"].isna().sum())
    print(f"\ncategory จาก filename: หาย {n_cat_missing:,} แถว · "
          f"{df['category'].nunique()} หมวด")

    # --- details: ข้อความ -> dict -> JSON string ---
    # เก็บเป็น JSON string ไม่ใช่ dict เพราะแต่ละแถวมี key ไม่เหมือนกัน (พบ 3,308 ชนิด)
    # ถ้าเก็บ dict ตรง ๆ ลงไฟล์ตาราง ระบบจะพยายามสร้างโครงสร้างที่กว้างเกินไปแล้วพังตอนอ่านกลับ
    details = df["details"].map(parse_details)
    n_with_keys = int((details.map(len) > 0).sum())
    df["details_json"] = details.map(lambda d: json.dumps(d, ensure_ascii=False))
    print(f"details: แปลงเป็น dict แล้วมี key อย่างน้อย 1 ตัว {n_with_keys:,} แถว "
          f"({n_with_keys / before * 100:.1f}%)")

    # --- ราคา: <= 0 ถือว่าไม่มีราคา แล้วตัดแถวที่ไม่มีราคาทิ้ง (การตัดสินข้อ 3) ---
    n_nonpositive = int((df["price"] <= 0).sum())
    n_na = int(df["price"].isna().sum())
    df = df[df["price"].notna() & (df["price"] > 0)].copy()
    print(f"\nราคา: หาย {n_na:,} แถว · <= 0 อีก {n_nonpositive:,} แถว")
    print(f"  ตัดทิ้งรวม {before - len(df):,} แถว -> เหลือ {len(df):,} แถว "
          f"({len(df) / before * 100:.1f}%)")

    # --- ล้างแท็ก HTML ที่ปนมาในคำอธิบาย (เจอ 23 แถว) ---
    has_html = df["description"].fillna("").astype(str).str.contains(HTML_TAG)
    n_html = int(has_html.sum())
    df.loc[has_html, "description"] = df.loc[has_html, "description"].map(strip_html)
    print(f"ล้างแท็ก HTML ในคำอธิบาย: {n_html:,} แถว")

    # --- ล้างไอคอน/อีโมจิใน features (ดูเหตุผลและกฎใน src/text_clean.py) ---
    before_items = int(df["features"].map(lambda v: len(v) if v is not None else 0).sum())
    before_chars = int(df["features"].map(
        lambda v: sum(len(str(x)) for x in v) if v is not None else 0).sum())

    df["features"] = df["features"].map(clean_text_list)

    after_items = int(df["features"].map(len).sum())
    after_chars = int(df["features"].map(lambda v: sum(len(x) for x in v)).sum())
    n_empty = int((df["features"].map(len) == 0).sum())
    print(f"\nล้าง features: {before_items:,} ข้อ -> {after_items:,} ข้อ "
          f"(หายไป {before_items - after_items:,} ข้อที่เหลือแต่ไอคอน)")
    print(f"  ตัวอักษร {before_chars:,} -> {after_chars:,} "
          f"(ลดลง {(before_chars - after_chars) / before_chars * 100:.1f}%)")
    print(f"  แถวที่ features ว่างหลังล้าง: {n_empty:,} ({n_empty / len(df) * 100:.1f}%)")

    # --- ล้างไอคอน/อีโมจิใน title และ description ด้วยกฎชุดเดียวกัน ---
    for column in ("title", "description"):
        original = df[column].fillna("").astype(str)
        dirty_before = int(original.str.contains(NON_ASCII).sum())

        cleaned = original.map(clean_text)
        blanked = cleaned.str.strip().eq("") & original.str.strip().ne("")

        if column == "title":
            # ชื่อสินค้าห้ามว่าง (quality gate บังคับ) — ถ้าล้างแล้วไม่เหลืออะไรให้คืนค่าเดิม
            # ชื่อที่อ่านไม่ออกยังดีกว่าไม่มีชื่อเลย
            cleaned = cleaned.where(~blanked, original)
            note = (f" · คืนค่าเดิมเพราะจะเหลือว่าง {int(blanked.sum()):,} แถว"
                    if int(blanked.sum()) else "")
        else:
            # คำอธิบายว่างได้ และ 41 แถวที่ล้างแล้วเหลือว่างนั้นตรวจแล้วเป็นขยะล้วน
            # ('...', '..', '/', '💐', '、') ไม่ใช่คำอธิบายจริง — ปล่อยว่างถูกต้องกว่าเก็บขยะไว้
            note = f" · กลายเป็นว่าง {int(blanked.sum()):,} แถว (เดิมเป็นขยะ เช่น '...' '/' '💐')"

        df[column] = cleaned
        dirty_after = int(cleaned.str.contains(NON_ASCII).sum())
        print(f"ล้าง {column}: แถวที่มีอักขระนอก ASCII {dirty_before:,} -> {dirty_after:,} "
              f"(ลดลง {(dirty_before - dirty_after) / max(dirty_before, 1) * 100:.1f}%)" + note)

    # ตัด `details` (แทนด้วย details_json แล้ว) และ `filename` (แทนด้วย category แล้ว)
    out = df.drop(columns=["details", "filename"]).reset_index(drop=True)

    # --- ด่านตรวจคุณภาพก่อนบันทึก ---
    print("\nตรวจคุณภาพ ...")
    check(len(out) > 0, "ไม่เหลือข้อมูลเลย")
    check(out["parent_asin"].is_unique, "รหัสสินค้า parent_asin ซ้ำ")
    check(out["parent_asin"].notna().all(), "มีแถวที่ไม่มีรหัสสินค้า")
    check(out["title"].notna().all(), "มีแถวที่ไม่มีชื่อสินค้า")
    check(out["category"].notna().all(), "มีแถวที่ไม่มีหมวด")
    check((out["price"] > 0).all(), "ยังมีราคาที่ <= 0 หลงเหลือ")
    check(out["average_rating"].between(1, 5).all(), "คะแนนอยู่นอกช่วง 1-5")
    check(out["details_json"].notna().all(), "มีแถวที่ details_json ว่าง")
    print("  ผ่านทุกข้อ")

    CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_feather(CLEAN_FILE)
    size_mb = CLEAN_FILE.stat().st_size / 1_048_576
    print(f"\nเขียน {CLEAN_FILE.relative_to(ROOT)} "
          f"({len(out):,} แถว × {out.shape[1]} คอลัมน์, {size_mb:,.1f} MB) "
          f"ใน {time.perf_counter() - started:.0f} วินาที")
    print(f"คอลัมน์: {', '.join(out.columns)}")
    return out


if __name__ == "__main__":
    clean()
