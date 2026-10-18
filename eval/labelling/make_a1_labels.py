"""สร้างไฟล์ป้าย ข ของแขน A1 ฝั่งไทยรอบ 4 — ให้ช่อง A1 เป็นค่าวัด ไม่ใช่ค่าอนุมาน

47 จาก 49 คำค้นในกอง g1 A1 หยิบสินค้าชุดเดียวกับ A3 และคำตอบเหมือนกัน จึงยกป้ายมาตรง ๆ
เหลือ q47 กับ q49 ที่ A1 หยิบไม่เหมือน ต้องอ่านคำตอบของ A1 เองแล้วติดป้ายใหม่
"""
import csv, io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
LAB = ROOT / "eval/labels"

raw = json.loads((ROOT / "eval/results/collection_th_20261013_1900.json").read_text(encoding="utf-8"))["raw"]
g1 = [g for g in raw["A1_r1"] if "g1" in g or "in_domain" in g][0]
A, B = raw["A1_r1"][g1], raw["A3_r1"][g1]

OWN = {
 "q47": (2, "", "A1 ปฏิเสธ ไม่หยิบสินค้าเลย คำตอบคือขอโทษว่าไม่พบของที่ตรง จึงไม่มีข้อความใดเกินข้อมูล "
                "(กฎพิเศษ: การบอกตรง ๆ ว่าของไม่ตรงถือว่าดี) ⚠ แต่ในกอง g1 การปฏิเสธคือความล้มเหลวของชั้นค้น "
                "ซึ่งป้าย ข ไม่ได้วัด"),
 "q49": (2, "", "A1 หยิบ 1 ชิ้นและใช้รูปแบบสำรอง คือยกช่อง details ดิบมาวางแทนการเขียนเหตุผลของตัวเอง "
                "จึงไม่มีข้อความที่โมเดลแต่งขึ้นเลย · เทียบกับ A3 (f48) ที่ได้ 0 เพราะเขียนสรรพคุณของเครื่อง "
                "เพลย์สเตชันเองทั้ง 3 ชิ้น ⚠ A1 ได้ 2 เพราะพูดน้อยกว่า ไม่ใช่เพราะบรรยายได้ดีกว่า"),
}

rows = []
src = {r["qid"]: r for r in csv.DictReader((LAB / "labels_b4_th_full.csv").open(encoding="utf-8-sig", newline=""))}
for qid, r in src.items():
    ta = [p["title"] for p in (A[qid].get("picked") or [])]
    tb = [p["title"] for p in (B[qid].get("picked") or [])]
    if qid in OWN:
        lb, kind, note = OWN[qid]
        rows.append({**r, "n_products": len(ta), "label": str(lb), "kind": kind, "note": note})
    else:
        assert ta == tb, f"{qid} หยิบไม่เหมือนแต่ไม่มีป้ายของ A1"
        rows.append({**r, "note": r["note"].rstrip() + " [A1 หยิบสินค้าชุดเดียวกับ A3 คำตอบเหมือนกัน ยกป้ายมา]"})

out = LAB / "labels_b4_th_a1.csv"
with out.open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

from collections import Counter
v = [int(r["label"]) for r in rows]; c = Counter(v)
b = [int(r["label"]) for r in src.values()]
print(f"เขียน {out.name} · {len(rows)} แถว")
print(f"  A3 ไทย  n=49 · 2={Counter(b)[2]:>2} 1={Counter(b)[1]:>2} 0={Counter(b)[0]:>2} · {sum(b)/(2*len(b))*100:.1f}%")
print(f"  A1 ไทย  n=49 · 2={c[2]:>2} 1={c[1]:>2} 0={c[0]:>2} · {sum(v)/(2*len(v))*100:.1f}%  <- ค่าวัด")
print(f"  ต่างกัน {sum(v)/(2*len(v))*100 - sum(b)/(2*len(b))*100:+.1f} จุด จาก 2 คำค้น (q47 q49)")
