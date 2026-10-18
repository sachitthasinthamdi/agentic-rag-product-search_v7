"""กรอกป้าย ข ลงไฟล์กองเต็ม — อ่านป้ายจาก batch.json ที่เขียนใหม่ทุกชุด

ใช้: python fill_b.py <รอบ>     (batch.json ต้องมี {"round": <รอบ>, "labels": {...}})
batch.json มี key "round" กันกรอกข้ามรอบ (บั๊กที่เคยทำให้ป้ายรอบ 4 ไหลไปทับรอบ 3)

เกณฑ์เดียวกับชุด 15 ข้อเดิม (labels_b3_th / labels_b4_th)
  0  ลอกคำค้นมาวางทั้ง 3 ชิ้นพร้อมมีชิ้นผิดประเภท · ชื่อสินค้าสั้นแล้วแต่งคุณสมบัติเองทั้งประโยค ·
     บรรยายตัวเครื่องแทนสินค้า
  1  ผิดคุณสมบัติ 1 อย่าง · ยกคุณสมบัติข้ามชิ้น · เติมคุณสมบัติที่ข้อมูลไม่บอก
  2  ทุกชิ้นตรงข้อมูล (รวมลอกชื่อสินค้ามาวางแต่ไม่เกินข้อมูล) · ตัวกรองทิ้งเหตุผลหมด
"""
import csv, io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
LAB = ROOT / "eval" / "labels"
rnd = sys.argv[1]
bf = Path(__file__).parent / "batch.json"
if not bf.exists():
    sys.exit(f"ยังไม่มี {bf.name} — ก๊อป batch.example.json เป็น batch.json "
             f"แล้วใส่ป้ายของชุดที่จะกรอก (ต้องมีคีย์ \"round\" ให้ตรงกับรอบที่สั่ง)")
b = json.loads(bf.read_text(encoding="utf-8"))
assert str(b["round"]) == str(rnd), f"batch.json เป็นของรอบ {b['round']} แต่สั่งกรอกรอบ {rnd}"
L = b["labels"]

FILES = {"3": "labels_b3_th_full.csv", "4": "labels_b4_th_full.csv",
         "en3": "labels_b3_full.csv",
         "en3_a1": "labels_b3_full_a1.csv",
         "en3_a3c": "labels_b3_full_a3c.csv",
         "th4_a1": "labels_b4_th_a1.csv"}
p = LAB / FILES[rnd]
rows = list(csv.DictReader(p.open(encoding="utf-8-sig", newline="")))
fields = list(rows[0]); filled = []
for r in rows:
    if r["label"].strip(): continue
    if r["ans_id"] in L:
        lb, kind, note = L[r["ans_id"]]
        r["label"], r["kind"], r["note"] = str(lb), kind, note
        filled.append(r["ans_id"])
with p.open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)
done = sum(1 for r in rows if r["label"].strip())
skipped = sorted(set(L) - set(filled))
print(f"กรอก {len(filled)} ข้อ: {' '.join(filled)}")
if skipped: print(f"ข้าม (ติดอยู่แล้ว): {' '.join(skipped)}")
print(f"รวมติดแล้ว {done}/{len(rows)} · เหลือ {len(rows)-done}")
