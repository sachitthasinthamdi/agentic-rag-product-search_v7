"""อัปชุดทดสอบใน `hf_upload/` ขึ้น HuggingFace

⚠ **ไม่รับโทเคนทางพารามิเตอร์หรือทางแชต** — ล็อกอินด้วยตัวเองก่อนในเทอร์มินัล

    hf auth login

สคริปต์นี้อ่านโทเคนที่ล็อกอินไว้แล้วเท่านั้น ถ้ายังไม่ได้ล็อกอินจะหยุดและบอกวิธี

⚠ **ตรวจก่อนอัปทุกครั้ง** สคริปต์จะลิสต์ไฟล์ที่จะอัปแล้วหยุดรอการยืนยัน
ถ้าไม่ใส่ `--yes` · การอัปขึ้นที่สาธารณะแล้วถอนทีหลังไม่ทันแล้ว เพราะอาจถูกแคชไว้

รัน:  python eval\\upload_hf_dataset.py --repo ชื่อผู้ใช้/ชื่อชุดข้อมูล --private
      python eval\\upload_hf_dataset.py --repo ... --private --yes
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "hf_upload"

MUST_HAVE = ["README.md", "NOTICE.md", "queries.csv", "qrels.csv",
             "answers.csv", "LICENSES/ESCI-Apache-2.0.txt",
             "LICENSES/WANDS-MIT.txt"]


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="อัปชุดทดสอบขึ้น HuggingFace")
    ap.add_argument("--repo", required=True, help="เช่น yourname/mark6-product-search")
    ap.add_argument("--private", action="store_true",
                    help="อัปแบบส่วนตัวก่อน (แนะนำ) แล้วค่อยเปิดสาธารณะทีหลัง")
    ap.add_argument("--yes", action="store_true", help="ข้ามการยืนยัน")
    args = ap.parse_args()

    missing = [f for f in MUST_HAVE if not (OUT / f).exists()]
    if missing:
        raise SystemExit("❌ ไฟล์ยังไม่ครบ: " + ", ".join(missing)
                         + "\n   รัน python eval\\build_hf_dataset.py ก่อน")

    try:
        from huggingface_hub import HfApi, whoami
    except ImportError:
        raise SystemExit("❌ ยังไม่มี huggingface_hub — pip install huggingface_hub")

    try:
        me = whoami()
    except Exception:                                            # noqa: BLE001
        raise SystemExit("❌ ยังไม่ได้ล็อกอิน — รัน `hf auth login` ในเทอร์มินัลก่อน\n"
                         "   ⚠ อย่าวางโทเคนลงในแชตหรือลงในโค้ด")
    print(f"ล็อกอินเป็น: {me.get('name')}")

    files = sorted(p for p in OUT.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)
    print(f"\nจะอัปขึ้น {args.repo} "
          f"({'ส่วนตัว' if args.private else '⚠ สาธารณะ'})")
    for p in files:
        print(f"  {p.relative_to(OUT).as_posix():<34}{p.stat().st_size:>8,} ไบต์")
    print(f"  รวม {len(files)} ไฟล์ · {total:,} ไบต์")

    if not args.private:
        print("\n⚠ กำลังจะอัปแบบ **สาธารณะ** — ใครก็เห็นได้และอาจถูกแคชไว้")
    if not args.yes:
        print("\nตรวจแล้วถ้าถูกต้อง รันซ้ำโดยเติม --yes")
        return

    api = HfApi()
    api.create_repo(args.repo, repo_type="dataset", private=args.private,
                    exist_ok=True)
    api.upload_folder(folder_path=str(OUT), repo_id=args.repo,
                      repo_type="dataset",
                      commit_message="Add Thai-English product search test collection")
    print(f"\n✅ เสร็จ — https://huggingface.co/datasets/{args.repo}")
    if args.private:
        print("   ตอนนี้เป็นส่วนตัว · เปิดสาธารณะได้ที่หน้า Settings ของชุดข้อมูล")


if __name__ == "__main__":
    main()
