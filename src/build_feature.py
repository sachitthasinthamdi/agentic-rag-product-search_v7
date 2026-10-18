"""ขั้นที่ 3 — สร้าง feature

จากข้อมูลที่ล้างแล้ว 12 คอลัมน์ → เพิ่ม 4 คอลัมน์ที่ระบบต้องใช้

ทำตาม `docs/feature_plan.md` กลุ่ม A:
  A1  embed_text   ข้อความก้อนเดียวสำหรับค้นหา (ใส่ทุก key ของ details ที่สินค้านั้นมี)
  A2  popularity   คะแนนความนิยมแบบ Bayesian
  A3  value_score  ความคุ้มค่า = คะแนน / ราคา
  A4  price_tier   ช่วงราคา ถูก/กลาง/แพง

**ไม่สกัด brand/color/material เป็นคอลัมน์** (ตัดสิน 2026-10-02) — ข้อมูลเหล่านั้น
ไปอยู่ใน embed_text ทั้งหมดแทน ถ้าภายหลังอยากได้คอลัมน์สำหรับกรอง ค่อยเพิ่มได้

รัน:  python src\\build_feature.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from features import build_embed_text, popularity, value_score   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN_FILE = ROOT / "data" / "clean" / "products_clean.feather"
FEATURE_FILE = ROOT / "data" / "feature" / "products_feature.feather"

# เกณฑ์จำนวนรีวิวขั้นต่ำของสูตร Bayesian — ใช้ควอนไทล์ที่ 75 ของทั้งคลัง
# สินค้าที่รีวิวน้อยกว่านี้จะถูกดึงเข้าหาค่าเฉลี่ยรวมมากขึ้นตามส่วน
POPULARITY_M_QUANTILE = 0.75

PRICE_TIER_LABELS = ["ถูก", "กลาง", "แพง"]

# ความยาวสูงสุดของ embed_text (ตั้งเป็น None เพื่อไม่ตัดเลย)
#
# ตัดสินใช้ 5,000 (2 ต.ค. 2026) จากการกระจายจริง: มัธยฐาน 1,909 · p95 3,867 · ยาวสุด 18,508
#   - ที่ 3,000 โดนตัด 15.7% ของแถว
#   - ที่ 5,000 โดนตัดราว 5%  <- เลือกอันนี้
# เหตุผลที่ยังต้องตัดอยู่: โมเดล embedding รับได้ยาวกว่านี้มาก แต่ข้อความยิ่งยาว
# ความหมายในเวกเตอร์ยิ่งถูกเฉลี่ยจนจาง สินค้าที่คำอธิบายยาว 18,000 ตัวอักษรจะค้นเจอยากขึ้น
EMBED_MAX_CHARS = 5000


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"❌ ไม่ผ่านการตรวจ: {message}")


def build() -> pd.DataFrame:
    started = time.perf_counter()
    print("อ่านข้อมูลที่ล้างแล้ว ...")
    df = pd.read_feather(CLEAN_FILE)
    n = len(df)
    print(f"  {n:,} แถว × {df.shape[1]} คอลัมน์")

    details = df["details_json"].map(json.loads)

    # --- A2 popularity -------------------------------------------------------
    mean_rating = float(df["average_rating"].mean())
    m = float(df["rating_number"].quantile(POPULARITY_M_QUANTILE))
    print(f"\nA2 popularity: C (คะแนนเฉลี่ยทั้งคลัง) = {mean_rating:.4f} · "
          f"m (รีวิวขั้นต่ำ ที่ควอนไทล์ {POPULARITY_M_QUANTILE}) = {m:,.0f}")
    df["popularity"] = [
        popularity(r, c, mean_rating, m)
        for r, c in zip(df["average_rating"], df["rating_number"], strict=True)
    ]
    print(f"   ต่ำสุด {df['popularity'].min():.3f} · มัธยฐาน {df['popularity'].median():.3f} "
          f"· สูงสุด {df['popularity'].max():.3f} · ว่าง {int(df['popularity'].isna().sum())}")

    # ตรวจว่าสูตรทำงานจริง: สินค้า 5 ดาวรีวิวเดียว ต้องแพ้ 4.5 ดาวรีวิวเยอะ
    fluke = df[(df["average_rating"] == 5.0) & (df["rating_number"] == 1)]["popularity"]
    solid = df[(df["average_rating"] >= 4.5) & (df["rating_number"] >= 1000)]["popularity"]
    if len(fluke) and len(solid):
        print(f"   ตรวจสอบ: 5 ดาวจากรีวิวเดียว (เฉลี่ย {fluke.mean():.3f}, {len(fluke):,} ชิ้น) "
              f"vs 4.5+ ดาวจาก 1,000+ รีวิว (เฉลี่ย {solid.mean():.3f}, {len(solid):,} ชิ้น)")

    # --- A3 value_score ------------------------------------------------------
    df["value_score"] = [
        value_score(r, p) for r, p in zip(df["average_rating"], df["price"], strict=True)
    ]
    vs = df["value_score"]
    print(f"\nA3 value_score: ว่าง {int(vs.isna().sum())} · เป็น 0 {int((vs == 0).sum())} "
          f"· ต่ำสุด {vs.min():.6f} · มัธยฐาน {vs.median():.4f} · สูงสุด {vs.max():.2f}")

    # --- A4 price_tier -------------------------------------------------------
    df["price_tier"] = pd.qcut(df["price"], q=3, labels=PRICE_TIER_LABELS).astype("object")
    edges = df["price"].quantile([0, 1 / 3, 2 / 3, 1]).round(2).tolist()
    print(f"\nA4 price_tier: ขอบช่วง ${edges[0]:,.2f} / ${edges[1]:,.2f} / "
          f"${edges[2]:,.2f} / ${edges[3]:,.2f}")
    for label, count in df["price_tier"].value_counts().reindex(PRICE_TIER_LABELS).items():
        print(f"   {label:<6} {count:,}")

    # --- A1 embed_text -------------------------------------------------------
    print(f"\nA1 embed_text: รวมทุก key ของ details (ตัดเฉพาะรหัส/วันที่) ...")
    df["embed_text"] = [
        build_embed_text(t, cat, s, f, d, det, EMBED_MAX_CHARS)
        for t, cat, s, f, d, det in zip(
            df["title"], df["category"], df["store"], df["features"],
            df["description"], details, strict=True)
    ]
    lengths = df["embed_text"].str.len()
    untruncated = [
        len(build_embed_text(t, cat, s, f, d, det, None))
        for t, cat, s, f, d, det in zip(
            df["title"], df["category"], df["store"], df["features"],
            df["description"], details, strict=True)
    ]
    full = pd.Series(untruncated)
    n_cut = int((full > EMBED_MAX_CHARS).sum())
    print(f"   ก่อนตัด: มัธยฐาน {full.median():,.0f} · p95 {full.quantile(.95):,.0f} "
          f"· ยาวสุด {full.max():,} ตัวอักษร")
    print(f"   ตัดที่ {EMBED_MAX_CHARS:,} ตัวอักษร -> โดนตัด {n_cut:,} แถว "
          f"({n_cut / n * 100:.1f}%)")
    print(f"   หลังตัด: มัธยฐาน {lengths.median():,.0f} · ว่าง {int((lengths == 0).sum())} แถว")

    # --- ด่านตรวจคุณภาพ ------------------------------------------------------
    print("\nตรวจคุณภาพ ...")
    check(len(df) == n, "จำนวนแถวเปลี่ยนไป")
    check(df["parent_asin"].is_unique, "รหัสสินค้าซ้ำ")
    check(df["popularity"].notna().all(), "popularity มีค่าว่าง")
    check(df["popularity"].between(1, 5).all(), "popularity อยู่นอกช่วง 1-5")
    check(df["value_score"].notna().all(), "value_score มีค่าว่าง")
    check((df["value_score"] > 0).all(), "value_score มีค่า <= 0")
    check(df["price_tier"].notna().all(), "price_tier มีค่าว่าง")
    check((df["embed_text"].str.len() > 0).all(), "embed_text ว่าง")
    print("  ผ่านทุกข้อ")

    FEATURE_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index(drop=True).to_feather(FEATURE_FILE)
    size_mb = FEATURE_FILE.stat().st_size / 1_048_576
    print(f"\nเขียน {FEATURE_FILE.relative_to(ROOT)} "
          f"({len(df):,} แถว × {df.shape[1]} คอลัมน์, {size_mb:,.1f} MB) "
          f"ใน {time.perf_counter() - started:.0f} วินาที")
    return df


if __name__ == "__main__":
    build()
