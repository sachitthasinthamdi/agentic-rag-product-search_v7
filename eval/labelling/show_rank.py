r"""แสดงคู่ที่ต้องติดป้ายทีละชุด — คู่กับ `make_rank_pairs.py`

พิมพ์คำค้น ชื่อสินค้า ราคา ร้าน และคำบรรยายจากคลัง ให้อ่านแล้วตัดสินป้ายได้
**ไม่บอกว่าแขนไหนหยิบของชิ้นนี้** (ดูเหตุผลใน `make_rank_pairs.py`)

ป้าย 4 ระดับตาม ESCI (Reddy et al. 2022)
    3 ตรงเป๊ะ        ใช่สิ่งที่ขอ ครบทุกเงื่อนไขที่ระบุ
    2 ใช้แทนได้      ไม่ใช่สิ่งที่ขอเป๊ะ แต่ผู้ใช้รับได้แทนกัน
    1 เกี่ยวข้อง     อยู่ในเรื่องเดียวกันแต่ใช้แทนไม่ได้ (อุปกรณ์เสริม ของคู่กัน)
    0 ไม่เกี่ยว      คนละสิ่ง

⚠ ของในกลุ่มที่มีงบ (รหัส b) **เกินงบ = ป้าย 0** ไม่ว่าจะตรงแค่ไหน
  เพราะผู้ใช้ระบุงบไว้ชัด การเสนอของเกินงบคือไม่ตอบโจทย์

รัน:  .venv\Scripts\python.exe eval\labelling\show_rank.py en 1 10
      (ภาษา · เริ่มที่คู่ที่ · จำนวนคู่)

กรอกป้ายด้วย:  .venv\Scripts\python.exe eval\labelling\fill_rank.py en a8en001=3 a8en002=0 ...
"""
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = {"en": "labels_a8_rank_en.csv", "th": "labels_a8_rank_th.csv"}


def rows(lang: str) -> list[dict]:
    path = ROOT / "eval/labels" / FILES[lang]
    if not path.exists():
        sys.exit(f"ยังไม่มี {path.name} — รัน make_rank_pairs.py {lang} ก่อน")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    if (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    lang = (sys.argv[1] if len(sys.argv) > 1 else "en").lower()
    if lang not in FILES:
        sys.exit(__doc__)
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    all_rows = rows(lang)
    todo = [r for r in all_rows if not (r["label"] or "").strip()]
    print(f"{FILES[lang]} · ทั้งหมด {len(all_rows)} คู่ · "
          f"ติดแล้ว {len(all_rows)-len(todo)} · เหลือ {len(todo)}\n")

    for r in todo[start - 1:start - 1 + count]:
        q = r["query_th"] or r["query"]
        budget = " ⚠ กลุ่มมีงบ เกินงบ = 0" if r["qid"].startswith("b") else ""
        price = f"${r['price']}" if r["price"] else "ไม่ระบุราคา"
        print("=" * 78)
        print(f"{r['pair_id']}  [{r['qid']}]{budget}")
        print(f"  ผู้ใช้ขอ : {q}")
        if r["query_th"] and r["query"]:
            print(f"  (อังกฤษ) : {r['query']}")
        print(f"  สินค้า   : {r['product_title']}")
        print(f"  ราคา/ร้าน: {price} · {r['store'] or '—'} · {r['category'] or '—'}")
        if r["details"]:
            print(f"  คำบรรยาย : {r['details'][:280]}")
        print()
    print(f"ถัดไป:  show_rank.py {lang} {start + count} {count}")


if __name__ == "__main__":
    main()
