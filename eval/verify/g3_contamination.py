"""กลุ่ม g3 ปนกัน — คำไหนคลังมีของจริง การปฏิเสธคำนั้นคือปฏิเสธผิด

นับจากกองป้าย: ถ้ามีสินค้าป้าย >= 2 (ตรงเป๊ะหรือใช้แทนได้) สำหรับคำค้นนั้น
แปลว่าคลังมีของ -> คำนั้นไม่ควรอยู่ใน g3 และการปฏิเสธคือ "ปฏิเสธผิด"
⚠ เป็นขอบล่าง เพราะกองป้ายมีแต่สินค้าที่แขนใดแขนหนึ่งหยิบมา
"""
import csv, io, json, sys
from collections import defaultdict
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
by_q = defaultdict(list)
for f in sorted((ROOT / "eval/labels").glob("labels_a*.csv")):
    if "check" in f.name or "pilot" in f.name: continue
    for r in csv.DictReader(f.open(encoding="utf-8-sig", newline="")):
        if r["label"].strip().isdigit(): by_q[r["qid"]].append(int(r["label"]))

for tag, fn in (("อังกฤษ", "collection_20261013_1329.json"),
                ("ไทย", "collection_th_20261013_1900.json")):
    raw = json.loads((ROOT / "eval/results" / fn).read_text(encoding="utf-8"))["raw"]
    g3 = [g for g in raw["A1_r1"] if "g3" in g or "out_of_domain" in g][0]
    g1 = [g for g in raw["A1_r1"] if "g1" in g or "in_domain" in g][0]
    ids = sorted(raw["A1_r1"][g3])
    has = [q for q in ids if max(by_q.get(q, [0])) >= 2]
    print(f"\n===== {tag}")
    print(f"  คำใน g3 ที่กองป้ายยืนยันว่าคลังมีของ (ป้าย >= 2): {len(has)}/{len(ids)}  {' '.join(has)}")
    for arm in ("A1_r1", "A3C_r1", "A3_r1"):
        R = raw[arm][g3]
        ref_all = [q for q in ids if not (R[q].get("picked") or [])]
        wrong_ref = [q for q in ref_all if q in has]
        true_g3 = [q for q in ids if q not in has]
        ok_true = sum(1 for q in true_g3 if not (R[q].get("picked") or []))
        # แนะนำได้ในกลุ่มคลังมีของ
        G1 = raw[arm][g1]
        sug = sum(1 for q in G1 if (G1[q].get("picked") or []))
        bal_old = (len(ref_all) / len(ids) + sug / len(G1)) / 2
        bal_new = (ok_true / len(true_g3) + sug / len(G1)) / 2
        print(f"  {arm[:3]:<4} ปฏิเสธ {len(ref_all)}/{len(ids)} · ในนั้น"
              f"ปฏิเสธผิด {len(wrong_ref)} คำ (คลังมีของ) · "
              f"ปฏิเสธถูกจริง {ok_true}/{len(true_g3)}")
        print(f"       คะแนนตัดสินใจ  ตามที่รายงาน {bal_old*100:5.1f}%  ·  "
              f"ถ้าตัด {len(has)} คำที่ปนออก {bal_new*100:5.1f}%")
