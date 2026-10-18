"""8 คำค้นที่ A3 ชนะ A1 ในกลุ่มนอกคลัง เป็นคำที่ควรหาเจอจริง หรือคำที่ควรปฏิเสธ

ถ้าเป็นคำที่ควรปฏิเสธ การที่ A3 ได้ nDCG สูงกว่าไม่ใช่ชัยชนะ
เพราะพฤติกรรมที่ถูกคือตอบว่าไม่พบ ซึ่งได้ nDCG = 0 โดยนิยาม
"""
import csv, io, json, sys
from math import log2
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
lab = {}
for f in sorted((ROOT / "eval/labels").glob("labels_a*.csv")):
    if "check" in f.name or "pilot" in f.name: continue
    for r in csv.DictReader(f.open(encoding="utf-8-sig", newline="")):
        if r["label"].strip().isdigit(): lab[(r["qid"], r["product_title"])] = int(r["label"])
IDCG = sum(3 / log2(i + 2) for i in range(3))

for tag, fn in (("อังกฤษ", "collection_20261013_1329.json"),
                ("ไทย", "collection_th_20261013_1900.json")):
    raw = json.loads((ROOT / "eval/results" / fn).read_text(encoding="utf-8"))["raw"]
    g3 = [g for g in raw["A1_r1"] if "g3" in g or "out_of_domain" in g][0]
    A, B = raw["A1_r1"][g3], raw["A3_r1"][g3]
    print(f"\n===== {tag} · กลุ่มนอกคลัง")
    nice = 0
    for q in sorted(set(A) & set(B)):
        pb = B[q].get("picked") or []
        gb = [lab.get((q, p["title"]), 0) for p in pb[:3]]
        nb = sum(v / log2(i + 2) for i, v in enumerate(gb)) / IDCG
        if nb <= 1e-12: continue
        pa = A[q].get("picked") or []
        tag2 = "A1 ปฏิเสธ" if not pa else f"A1 หยิบ {len(pa)}"
        ok = max(gb) >= 2
        nice += ok
        print(f"  {q}  nDCG(A3) {nb:.3f}  ป้าย {gb}  {tag2:<11} "
              f"{'<- มีของตรง/ใช้แทนได้จริง คำนี้ไม่ควรอยู่ใน g3' if ok else '<- ป้ายสูงสุดแค่ 1 คือของเสริม'}")
        print(f"      «{B[q]['q'][:70]}»")
    print(f"  สรุป: {nice} คำที่ A3 ชนะเป็นคำที่คลังมีของตรงหรือใช้แทนได้จริง")
