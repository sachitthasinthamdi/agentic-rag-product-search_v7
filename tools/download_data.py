"""โหลดข้อมูลที่เตรียมไว้แล้วจาก HuggingFace ลงเครื่อง

ชุดข้อมูล `sachittha/amazon-products-agentic-rag` มีคลังสินค้าที่ผ่านการล้าง
และสกัดคุณลักษณะแล้ว พร้อมเวกเตอร์ที่ฝังไว้แล้ว จึง**ข้ามขั้นตอนเตรียมข้อมูล
ทั้งหมดได้** เหลือแค่สร้างดัชนีค้นหาขั้นเดียว

รัน:  python tools\\download_data.py
      python tools\\download_data.py --testcollection   (โหลดชุดทดสอบด้วย)

ไฟล์ที่ได้
    data/feature/products_feature.feather      คลัง 81,264 แถว 16 คอลัมน์
    data/vectors/bge-m3_v1.npy                 เวกเตอร์ 81,264 x 1,024
    data/vectors/bge-m3_v1.ids.feather         รหัสสินค้าเรียงตรงกับเวกเตอร์
    data/vectors/bge-m3_v1.meta.json           ข้อมูลกำกับของรอบที่ฝัง

ไม่ต้องใช้โทเคน เพราะทั้งสองชุดเป็นสาธารณะ
"""
from __future__ import annotations

import argparse
import io
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

CATALOGUE_REPO = "sachittha/amazon-products-agentic-rag"
TESTSET_REPO = "sachittha/thai-English-product-search-testcollection"

# (ไฟล์บน HuggingFace, ที่เก็บในเครื่อง)
CATALOGUE_FILES = [
    ("data/products_feature.feather",    DATA / "feature" / "products_feature.feather"),
    ("vectors/bge-m3_v1.npy",            DATA / "vectors" / "bge-m3_v1.npy"),
    ("vectors/bge-m3_v1.ids.feather",    DATA / "vectors" / "bge-m3_v1.ids.feather"),
    ("vectors/bge-m3_v1.meta.json",      DATA / "vectors" / "bge-m3_v1.meta.json"),
]

TESTSET_FILES = [
    ("queries.csv", DATA / "testcollection" / "queries.csv"),
    ("qrels.csv",   DATA / "testcollection" / "qrels.csv"),
    ("answers.csv", DATA / "testcollection" / "answers.csv"),
]


def fetch(repo: str, items, force: bool) -> None:
    from huggingface_hub import hf_hub_download

    for remote, local in items:
        if local.exists() and not force:
            size = local.stat().st_size / 1_048_576
            print(f"  ข้าม  {local.relative_to(ROOT)}  (มีอยู่แล้ว {size:,.1f} MB)")
            continue
        print(f"  โหลด  {remote}  ...", end="", flush=True)
        cached = hf_hub_download(repo_id=repo, filename=remote, repo_type="dataset")
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(cached, local)
        size = local.stat().st_size / 1_048_576
        print(f" เสร็จ  {size:,.1f} MB  ->  {local.relative_to(ROOT)}")


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(description="โหลดข้อมูลที่เตรียมไว้แล้วจาก HuggingFace")
    ap.add_argument("--testcollection", action="store_true",
                    help="โหลดชุดทดสอบพร้อมเฉลยด้วย (ไม่จำเป็นถ้าใช้ไฟล์ในโปรเจกต์)")
    ap.add_argument("--force", action="store_true",
                    help="โหลดทับไฟล์ที่มีอยู่แล้ว")
    args = ap.parse_args()

    try:
        import huggingface_hub                                   # noqa: F401
    except ImportError:
        sys.exit("ยังไม่ได้ติดตั้ง huggingface_hub — รัน  pip install -r requirements.txt  ก่อน")

    print(f"คลังสินค้าและเวกเตอร์  จาก {CATALOGUE_REPO}")
    fetch(CATALOGUE_REPO, CATALOGUE_FILES, args.force)

    if args.testcollection:
        print(f"\nชุดทดสอบและเฉลย  จาก {TESTSET_REPO}")
        fetch(TESTSET_REPO, TESTSET_FILES, args.force)

    print("\nเสร็จแล้ว ขั้นต่อไปคือสร้างดัชนีค้นหา")
    print("    python src\\build_index.py --reset")


if __name__ == "__main__":
    main()
