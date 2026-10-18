"""ขั้นที่ 4.4 — สร้างฐานข้อมูลเวกเตอร์ (Chroma local) จากไฟล์ `.npy`

**ไม่แปลงเวกเตอร์ใหม่** — อ่านจากไฟล์ที่ `embed.py` ทำไว้แล้ว ใช้เวลาไม่กี่นาที
นี่คือเหตุผลที่แยกเก็บเวกเตอร์เป็นไฟล์: สร้างฐานใหม่ได้ตลอดโดยไม่ต้องรอ 53 นาที

**ตรวจความสอดคล้องก่อนสร้าง** — เทียบ sha256 ของ `embed_text` ปัจจุบันกับที่บันทึกไว้ใน
`.meta.json` ถ้าไม่ตรงแปลว่าข้อความถูกแก้หลังแปลงเวกเตอร์ → เวกเตอร์ล้าสมัย ต้องแปลงใหม่
(ถ้าไม่ตรวจ จะไม่มีใครรู้จนกระทั่งผลค้นเพี้ยนแบบอธิบายไม่ได้)

ชื่อ collection = `products_bge-m3_v1` — บอกโมเดลและเวอร์ชันของ `embed_text`
ถ้าวันหนึ่งแก้ `embed_text` ก็สร้าง `v2` อยู่ด้วยกันได้ เทียบผลข้ามเวอร์ชันได้

รัน:  python src\\build_index.py [--reset]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import chromadb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed import TAG, VECTOR_DIR, text_fingerprint   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEATURE_FILE = ROOT / "data" / "feature" / "products_feature.feather"
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION = f"products_{TAG}"

# ฟิลด์ที่เก็บเป็น metadata — **เก็บเกินไว้ดีกว่าขาด**
# การเพิ่มฟิลด์ทีหลังต้องวนอัปเดตทั้ง 81,264 รายการ และสถาปัตยกรรมต่างกันใช้ฟิลด์ต่างกัน
# (อันหนึ่งเรียงด้วย popularity อีกอันใช้ value_score อีกอันกรอง price_tier)
METADATA_FIELDS = [
    "title", "category", "price", "price_tier",
    "average_rating", "rating_number", "popularity", "value_score",
    "store", "image",
]
# ไม่เก็บ: description, features, details_json, categories
#   ยาวมาก และอยู่ใน document (embed_text) แล้ว · ถ้าต้องการเปิดจาก .feather ด้วย parent_asin

ADD_BATCH = 2_000     # จำนวนรายการต่อการเรียก collection.add หนึ่งครั้ง


def clean_metadata(record: dict) -> dict:
    """Chroma รับ metadata เฉพาะ str/int/float/bool และ **ห้ามเป็น None**
    ค่าที่หายจึงต้อง *ตัด key ทิ้ง* ไม่ใช่ใส่ None
    (ตัวกรอง `$eq` จะไม่ match รายการที่ไม่มี key นั้น ซึ่งเป็นพฤติกรรมที่ถูกต้อง)
    """
    out = {}
    for key, value in record.items():
        if value is None or (isinstance(value, float) and value != value):
            continue
        out[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
    return out


def load_vectors() -> tuple[np.ndarray, pd.DataFrame, dict]:
    npy_file = VECTOR_DIR / f"{TAG}.npy"
    ids_file = VECTOR_DIR / f"{TAG}.ids.feather"
    meta_file = VECTOR_DIR / f"{TAG}.meta.json"

    for path in (npy_file, ids_file, meta_file):
        if not path.exists():
            raise SystemExit(f"❌ ไม่พบ {path.relative_to(ROOT)} — รัน `python src\\embed.py` ก่อน")

    vectors = np.load(npy_file)
    ids = pd.read_feather(ids_file)
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    return vectors, ids, meta


def build(reset: bool = False) -> None:
    started = time.perf_counter()
    vectors, ids, meta = load_vectors()
    print(f"อ่านเวกเตอร์: {vectors.shape[0]:,} × {vectors.shape[1]} ({vectors.dtype})")
    print(f"  โมเดล {meta['model']} · เวอร์ชัน {meta['version']} · สร้างเมื่อ {meta['created_at']}")

    print("\nอ่านชั้น feature ...")
    df = pd.read_feather(FEATURE_FILE,
                         columns=["parent_asin", "embed_text", *METADATA_FIELDS])

    # --- ตรวจความสอดคล้อง 3 ชั้น ---
    print("ตรวจความสอดคล้องระหว่างเวกเตอร์กับข้อมูล ...")
    if len(df) != vectors.shape[0]:
        raise SystemExit(f"❌ จำนวนไม่ตรง: เวกเตอร์ {vectors.shape[0]:,} แต่ข้อมูล {len(df):,} แถว")
    if not (df["parent_asin"].values == ids["parent_asin"].values).all():
        raise SystemExit("❌ ลำดับ parent_asin ไม่ตรงกับตอนแปลงเวกเตอร์")

    current = text_fingerprint(df["embed_text"])
    if current != meta["embed_text_sha256"]:
        raise SystemExit(
            "❌ `embed_text` ถูกแก้หลังจากแปลงเวกเตอร์แล้ว → เวกเตอร์ล้าสมัย\n"
            f"   ตอนแปลง: {meta['embed_text_sha256'][:16]}...\n"
            f"   ปัจจุบัน: {current[:16]}...\n"
            "   ต้องรัน `python src\\embed.py` ใหม่ (หรือขึ้นเวอร์ชันเป็น v2)")
    print("  ผ่าน — จำนวนตรง · ลำดับตรง · ข้อความตรงกับที่ใช้แปลงเวกเตอร์")

    # --- สร้าง collection ---
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if reset and COLLECTION in [c.name for c in client.list_collections()]:
        print(f"\nลบ collection '{COLLECTION}' เดิมแล้วสร้างใหม่")
        client.delete_collection(COLLECTION)
    collection = client.get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"})

    existing = collection.count()
    if existing >= len(df):
        print(f"\ncollection '{COLLECTION}' มีครบแล้ว {existing:,} รายการ — ข้าม "
              f"(ใช้ --reset เพื่อสร้างใหม่)")
        return
    if existing:
        print(f"\ncollection มีอยู่แล้ว {existing:,} รายการ — เพิ่มต่อจากนั้น")

    print(f"\nใส่ข้อมูลลง '{COLLECTION}' ...")
    documents = df["embed_text"].tolist()
    all_ids = df["parent_asin"].tolist()
    metadatas = df[METADATA_FIELDS].to_dict(orient="records")

    for start in range(existing, len(df), ADD_BATCH):
        stop = min(start + ADD_BATCH, len(df))
        collection.add(
            ids=all_ids[start:stop],
            embeddings=vectors[start:stop].astype(np.float32).tolist(),
            documents=documents[start:stop],
            metadatas=[clean_metadata(m) for m in metadatas[start:stop]],
        )
        if stop % 20_000 < ADD_BATCH or stop == len(df):
            print(f"   {stop:,}/{len(df):,} ({stop / len(df) * 100:.0f}%)")

    final = collection.count()
    size_mb = sum(f.stat().st_size for f in CHROMA_DIR.rglob("*") if f.is_file()) / 1_048_576
    print(f"\nเสร็จใน {(time.perf_counter() - started) / 60:.1f} นาที")
    print(f"  collection '{COLLECTION}' มี {final:,} รายการ · โฟลเดอร์ {size_mb:,.0f} MB")
    if final != len(df):
        raise SystemExit(f"❌ ใส่ไม่ครบ: คาด {len(df):,} ได้ {final:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="สร้าง Chroma จากไฟล์เวกเตอร์")
    parser.add_argument("--reset", action="store_true", help="ลบ collection เดิมแล้วสร้างใหม่")
    build(parser.parse_args().reset)


if __name__ == "__main__":
    main()
