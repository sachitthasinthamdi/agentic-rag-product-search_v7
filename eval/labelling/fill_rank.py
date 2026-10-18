r"""กรอกป้ายลงไฟล์ `labels_a8_rank_*.csv` — คู่กับ `show_rank.py`

**ทำไมต้องมีไฟล์นี้ ไม่แก้ CSV ด้วยมือ** รอบก่อน `fill_b.py` รุ่นแรกเก็บป้าย
ไว้ในสคริปต์แล้วรหัสคู่ชนกันข้ามรอบ → **ป้ายรอบ 3 ถูกเขียนทับ 34 แถวแบบเงียบ ๆ**
(docs/steps.md) ไฟล์นี้จึง
  1. รับป้ายจาก**บรรทัดคำสั่ง** ไม่เก็บไว้ในโค้ด
  2. **ปฏิเสธการเขียนทับ** คู่ที่มีป้ายอยู่แล้ว เว้นแต่สั่ง --force
  3. พิมพ์รหัสที่กรอกจริงออกมาให้ตรวจ

รัน:  .venv\Scripts\python.exe eval\labelling\fill_rank.py en a8en001=3 a8en002=0
      .venv\Scripts\python.exe eval\labelling\fill_rank.py en a8en003=2 --note "ยี่ห้ออื่น"
      .venv\Scripts\python.exe eval\labelling\fill_rank.py en --force a8en001=2

กรอกทีละมาก ๆ พร้อมเหตุผลรายคู่ ใช้ `--from` อ่านไฟล์ที่แต่ละบรรทัดเป็น
`รหัสคู่ <แท็บ> ป้าย <แท็บ> เหตุผล` (บรรทัดว่างและบรรทัดที่เริ่มด้วย # ข้ามไป)
วิธีนี้ปลอดภัยกว่าแปะป้ายไว้ในโค้ด และยังกันเขียนทับเหมือนเดิม

      .venv\Scripts\python.exe eval\labelling\fill_rank.py en --from docs/labels_a8_en.tsv
"""
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = {"en": "labels_a8_rank_en.csv", "th": "labels_a8_rank_th.csv",
         "en9": "labels_a9_rank_en.csv", "th9": "labels_a9_rank_th.csv"}
VALID = {"0", "1", "2", "3"}


def main() -> None:
    if (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    args = sys.argv[1:]
    if not args or args[0].lower() not in FILES:
        sys.exit(__doc__)
    lang = args.pop(0).lower()

    force = "--force" in args
    args = [a for a in args if a != "--force"]
    note = ""
    if "--note" in args:
        i = args.index("--note")
        note = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]

    want: dict[str, str] = {}
    notes: dict[str, str] = {}
    if "--from" in args:
        i = args.index("--from")
        if i + 1 >= len(args):
            sys.exit("--from ต้องตามด้วยชื่อไฟล์")
        src = Path(args[i + 1])
        if not src.is_absolute():
            src = ROOT / src
        del args[i:i + 2]
        for ln, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                sys.exit(f"{src.name} บรรทัด {ln}: ต้องมี รหัสคู่<แท็บ>ป้าย")
            pid, val = parts[0].strip(), parts[1].strip()
            if val not in VALID:
                sys.exit(f"{src.name} บรรทัด {ln}: ป้ายต้องเป็น 0 1 2 3 — ได้ {val!r}")
            want[pid] = val
            if len(parts) > 2 and parts[2].strip():
                notes[pid] = parts[2].strip()

    for a in args:
        if "=" not in a:
            sys.exit(f"รูปแบบต้องเป็น รหัสคู่=ป้าย เช่น a8en001=3 — ได้ {a!r}")
        pid, val = a.split("=", 1)
        if val.strip() not in VALID:
            sys.exit(f"ป้ายต้องเป็น 0 1 2 หรือ 3 — {pid} ได้ {val!r}")
        want[pid.strip()] = val.strip()
    if not want:
        sys.exit(__doc__)

    path = ROOT / "eval/labels" / FILES[lang]
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = list(reader.fieldnames or []), list(reader)

    known = {r["pair_id"] for r in rows}
    unknown = sorted(set(want) - known)
    if unknown:
        sys.exit(f"ไม่มีรหัสคู่เหล่านี้ในไฟล์: {' '.join(unknown)}")

    filled, refused = [], []
    for r in rows:
        pid = r["pair_id"]
        if pid not in want:
            continue
        if (r["label"] or "").strip() and not force:
            refused.append(f"{pid} (มีป้าย {r['label']} อยู่แล้ว)")
            continue
        r["label"] = want[pid]
        if notes.get(pid):
            r["note"] = notes[pid]
        elif note:
            r["note"] = note
        filled.append(f"{pid}={want[pid]}")

    if refused:
        print("⚠ ไม่เขียนทับ: " + " · ".join(refused))
        print("   ถ้าต้องการเขียนทับจริง ใส่ --force")
    if not filled:
        sys.exit("ไม่ได้กรอกอะไรเลย")

    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    left = sum(1 for r in rows if not (r["label"] or "").strip())
    print(f"กรอกแล้ว {len(filled)} คู่: {' '.join(filled)}")
    print(f"{path.name} · เหลือที่ยังไม่ติดป้าย {left} คู่")


if __name__ == "__main__":
    main()
