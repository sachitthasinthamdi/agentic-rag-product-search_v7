"""A1 เทียบ A3C และ A3 แบบจับคู่ทีละคำค้น — nDCG@3 ต่อคำค้น + ทดสอบนัยสำคัญ

ต่างจากตารางสรุปที่เทียบค่าเฉลี่ย ตัวนี้เทียบคำค้นเดียวกันตรง ๆ จึงบอกได้ว่า
ส่วนต่างมาจากคำค้นกี่คำ และแยกจากความบังเอิญได้ไหม
p = การสุ่มสลับเครื่องหมายแบบนับครบทุกกรณี (คอนโวลูชันการกระจายผลรวม)
"""
import csv, io, json, sys
from collections import Counter, defaultdict
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

IDCG = sum((3) / log2(i + 2) for i in range(3))

def ndcg(rec):
    picked = rec.get("picked") or []
    g = [lab.get((rec["_qid"], p["title"]), 0) for p in picked[:3]]
    return sum(v / log2(i + 2) for i, v in enumerate(g)) / IDCG

def exact_p(diffs, scale=1000):
    nz = [round(abs(d) * scale) for d in diffs if abs(d) > 1e-12]
    obs = round(abs(sum(d for d in diffs if abs(d) > 1e-12)) * scale)
    if not nz: return 1.0, 0
    dist = {0: 1}
    for d in nz:
        nxt = defaultdict(int)
        for s, c in dist.items(): nxt[s + d] += c; nxt[s - d] += c
        dist = nxt
    return sum(c for s, c in dist.items() if abs(s) >= obs) / 2 ** len(nz), len(nz)

GNAME = {"group1_in_domain": "คลังมีของ (g1)", "group3_out_of_domain": "นอกคลัง (g3)",
         "group4_budget": "มีเงื่อนไขราคา (g4)", "g1": "คลังมีของ (g1)",
         "g3": "นอกคลัง (g3)", "g4": "มีเงื่อนไขราคา (g4)"}

for tag, fn in (("อังกฤษ", "collection_20261013_1329.json"),
                ("ไทย", "collection_th_20261013_1900.json")):
    raw = json.loads((ROOT / "eval/results" / fn).read_text(encoding="utf-8"))["raw"]
    print(f"\n{'='*78}\n  {tag}\n{'='*78}")
    for other in ("A3C_r1", "A3_r1"):
        print(f"\n--- A1 เทียบ {other.replace('_r1','')} ---")
        tot_w = tot_l = 0
        for g in raw["A1_r1"]:
            A, B = raw["A1_r1"][g], raw[other][g]
            ids = sorted(set(A) & set(B))
            if not ids: continue
            diffs = []
            for q in ids:
                a, b = dict(A[q]), dict(B[q]); a["_qid"] = b["_qid"] = q
                diffs.append(ndcg(b) - ndcg(a))      # บวก = แขนที่เทียบดีกว่า A1
            up = sum(1 for d in diffs if d > 1e-12); dn = sum(1 for d in diffs if d < -1e-12)
            tot_w += dn; tot_l += up
            p, k = exact_p(diffs)
            mean_d = sum(diffs) / len(diffs)
            verdict = ("A1 แพ้" if mean_d > 0 else "A1 ชนะ" if mean_d < 0 else "เสมอ")
            sig = "มีนัยสำคัญ" if p < 0.05 else "แยกจากความบังเอิญไม่ได้"
            print(f"  {GNAME.get(g,g):<18} n={len(ids):>3} · nDCG ต่าง {mean_d:+.4f} ({verdict}) · "
                  f"{other[:3]} ดีกว่า {up} คำ · A1 ดีกว่า {dn} คำ · เท่ากัน {len(ids)-up-dn} คำ · "
                  f"p = {p:.4f} {sig}")
        print(f"  รวมทุกกลุ่ม: A1 ชนะ {tot_w} คำ · แพ้ {tot_l} คำ")

        # การตัดสินใจแนะนำ/ปฏิเสธ
        for g, want in (("group3_out_of_domain", "ปฏิเสธ"), ("g3", "ปฏิเสธ")):
            if g not in raw["A1_r1"]: continue
            A, B = raw["A1_r1"][g], raw[other][g]
            ids = sorted(set(A) & set(B))
            a_ok = sum(1 for q in ids if not (A[q].get("picked") or []))
            b_ok = sum(1 for q in ids if not (B[q].get("picked") or []))
            flip = sum(1 for q in ids if not (A[q].get("picked") or []) and (B[q].get("picked") or []))
            print(f"  {'ปฏิเสธถูกในกลุ่มนอกคลัง':<18} A1 {a_ok}/{len(ids)} · "
                  f"{other[:3]} {b_ok}/{len(ids)} · คำที่ A1 ปฏิเสธถูกแต่ {other[:3]} ยัดของมา {flip}")
