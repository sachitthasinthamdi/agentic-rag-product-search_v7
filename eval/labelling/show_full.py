"""พิมพ์คำตอบที่ยังไม่ได้ติดป้าย แบบกระชับ — ชื่อสินค้า + รายละเอียด + เหตุผลที่ระบบเขียน"""
import csv, io, json, re, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
# รอบ -> (ไฟล์ผล, ไฟล์ป้าย, ชื่อกลุ่มในไฟล์ผล)
RES = {
  "3":   ("collection_th_20261013_1506.json", "labels_b3_th_full.csv", "g1"),
  "4":   ("collection_th_20261013_1900.json", "labels_b4_th_full.csv", "g1"),
  "en3": ("collection_20261013_1329.json",    "labels_b3_full.csv",    "g1"),
  "en3_a1":  ("collection_20261013_1329.json", "labels_b3_full_a1.csv",  "g1"),
  "en3_a3c": ("collection_20261013_1329.json", "labels_b3_full_a3c.csv", "g1"),
}
rnd, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 else "A3"   # แขนที่จะอ่านคำตอบ
res_file, lab_file, grp = RES[rnd]
raw = json.loads((ROOT / "eval/results" / res_file).read_text(encoding="utf-8"))["raw"][f"{arm}_r1"][grp]
rows = [r for r in csv.DictReader(
    (ROOT / "eval/labels" / lab_file).open(encoding="utf-8-sig", newline=""))
    if not r["label"].strip()]
def reasons(reply):
    out, blk = [], []
    for ln in reply.split("\n"):
        if re.match(r"^\d+\.\s", ln):
            if len(blk) >= 3: out.append(blk[2].strip())
            blk = [ln]
        else: blk.append(ln)
    if len(blk) >= 3: out.append(blk[2].strip())
    return out
print(f"ยังไม่ติด {len(rows)} ข้อ · แสดงข้อที่ {lo}-{min(hi,len(rows))}\n")
for r in rows[lo-1:hi]:
    rec = raw[r["qid"]]
    print("=" * 76)
    print(f'{r["ans_id"]} · {r["qid"]} · ผู้ใช้ขอ: {rec["q"]}   echoed={rec.get("echoed")}')
    rs = reasons(rec["reply"])
    for i, p in enumerate(rec["picked"], 1):
        det = (p.get("details") or "")
        det = det.split("| Brand:")[-1] if "| Brand:" in det else det
        print(f'  [{i}] {p["title"]}')
        if det.strip(): print(f'      ข้อมูล: {det.strip()[:300]}')
        print(f'      ระบบเขียน: {rs[i-1] if i-1 < len(rs) else "(ว่าง)"}')
    print()
