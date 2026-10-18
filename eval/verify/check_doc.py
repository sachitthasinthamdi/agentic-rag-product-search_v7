r"""กวาดตัวเลขในเอกสารสรุปโครงงาน — หาตัวเลขค้างของรันรุ่นก่อน และตรวจว่าค่าที่ควรมีอยู่ครบ

ต้องมีสำเนาเอกสารก่อน เพราะเอกสารอยู่บน Claude Docs ไม่ได้อยู่ในโฟลเดอร์นี้
  1) อ่านเอกสารด้วยเครื่องมือ docs แล้วเซฟฟิลด์ data.xml ลงไฟล์
  2) .venv\Scripts\python.exe eval\verify\check_doc.py <พาธไฟล์นั้น>

ค่าที่ควรมีคำนวณสด ๆ จากไฟล์ผลและไฟล์ป้าย ไม่ได้พิมพ์มือ

⚠ บทเรียนข้อ 219 — ถ้าสคริปต์นี้บอกว่าค่าไหนไม่ตรง **ให้ไปหาสคริปต์ที่ผลิตเลขนั้นมารันซ้ำก่อน**
ตัวหารที่ต่างกัน (เช่นตัดคำตอบ weak ออกหรือไม่) ทำให้ดูเหมือนเล่มผิดได้ทั้งที่เล่มถูก
"""
from __future__ import annotations

import csv
import html
import io
import re
import sys
from math import log2
from pathlib import Path

def _utf8() -> None:
    """บังคับ stdout เป็น utf-8 — เรียกจาก main เท่านั้น
    ถ้าห่อตอน import สคริปต์ที่ import ไฟล์นี้จะเจอ stdout ปิดไปแล้ว"""
    if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_counts as rc  # noqa: E402

# ตัวเลขของรันรุ่นก่อนที่ต้องไม่มีในเล่มแล้ว
STALE = {
    "0.554": "nDCG g1 อังกฤษรุ่นก่อน (ตอนนี้ 0.559)",
    "0.542": "nDCG g1 ไทยรุ่นก่อน (ตอนนี้ 0.536/0.543)",
    "0.549": "nDCG g1 ไทยรุ่นก่อน",
    "0.490": "nDCG g4 ไทยรุ่นก่อน (ตอนนี้ 0.497/0.508)",
    "0.502": "nDCG g4 ไทยรุ่นก่อน",
    "498 คู่": "จำนวนป้าย ก รุ่นก่อน (ตอนนี้ 506)",
    "115 นาที": "เวลารวมรุ่นก่อน (ตอนนี้ 95.6)",
    "ช้ากว่า 62%": "ส่วนต่างเวลารุ่นก่อน (ตอนนี้ 36%)",
    "ราคาเพิ่ม 62%": "ส่วนต่างเวลารุ่นก่อน",
    "105 คำตอบ": "จำนวนคำตอบป้าย ข ก่อนขยายกอง (ตอนนี้ 222)",
    "ค่าอนุมาน": "ช่อง A1 ฝั่งไทยเป็นค่าวัดแล้ว",
    "±4.1": "ขอบเขตความคลาดของช่อง A1 ที่ไม่ต้องใช้แล้ว",
}


def expected() -> dict[str, str]:
    """ค่าที่ควรปรากฏในเล่ม คำนวณสดจากไฟล์"""
    out: dict[str, str] = {}
    lab = rc.load_a_labels()
    tot = sum(1 for f in sorted(rc.LAB.glob("labels_a*.csv"))
              if "check" not in f.name and "pilot" not in f.name
              for r in csv.DictReader(f.open(encoding="utf-8-sig", newline=""))
              if r["label"].strip().isdigit())
    out["ป้าย ก (คู่)"] = str(tot)
    for fn in ("labels_b3_th_full.csv", "labels_b4_th_full.csv", "labels_b4_th_a1.csv",
               "labels_b3_th.csv", "labels_b4_th.csv"):
        if (rc.LAB / fn).exists():
            out[f"ป้าย ข {fn}"] = f"{rc.b_score(fn)[2]:.1f}"
    import json
    for tag, fn in rc.RUNS:
        raw = json.loads((rc.RES / fn).read_text(encoding="utf-8"))["raw"]
        for arm in rc.ARMS:
            rows = [r for g in raw[arm] for r in raw[arm][g].values()]
            n = len(rows)
            for g in raw[arm]:
                k = rc.group_of(g)
                v = sum(rc.ndcg(raw[arm][g][q], q, lab) for q in raw[arm][g]) / len(raw[arm][g])
                out[f"nDCG {tag} {arm[:3]} {k}"] = f"{v:.3f}"
            out[f"LLM/ข้อ {tag} {arm[:3]}"] = f"{sum(r['llm_calls'] for r in rows)/n:.2f}"
            out[f"เวลา/ข้อ {tag} {arm[:3]}"] = f"{sum(r['seconds'] for r in rows)/n:.1f}"
            out[f"ได้ครบ 3 ชิ้น {tag} {arm[:3]}"] = str(
                sum(1 for r in rows if len(r.get("picked") or []) == 3))
    return out


def main() -> None:
    _utf8()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"</(row|cell)>", " | ", raw)))

    print("=" * 78)
    print("  ก · ตัวเลขค้างของรันรุ่นก่อน")
    print("=" * 78)
    bad = 0
    for pat, why in STALE.items():
        if pat in text:
            bad += 1
            k = text.find(pat)
            print(f"  ⚠ พบ «{pat}» — {why}")
            print(f"      …{text[max(0,k-90):k+70].strip()}…")
    if not bad:
        print("  ✅ ไม่พบตัวเลขค้างเลย")

    print()
    print("=" * 78)
    print("  ข · ค่าที่ควรมีในเล่ม (คำนวณสดจากไฟล์ผลและไฟล์ป้าย)")
    print("=" * 78)
    miss = 0
    for name, v in expected().items():
        ok = v in text or v.rstrip("0").rstrip(".") in text
        if not ok:
            miss += 1
        print(f"  {'✅' if ok else '❌ ไม่พบ'} {name:<32} = {v}")
    print(f"\n  สรุป: ตัวเลขค้าง {bad} แบบ · ค่าที่ไม่พบ {miss} ค่า")
    print("  ⚠ ค่าที่ไม่พบอาจเป็นค่าที่เล่มไม่จำเป็นต้องอ้าง ไม่ใช่ข้อผิดพลาดทุกครั้ง")


if __name__ == "__main__":
    main()
