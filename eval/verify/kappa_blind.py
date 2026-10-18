"""κ หลังตัด 3 คู่ที่ไม่ปิดตา + ดูทิศทางความต่าง + สัดส่วนป้ายที่ AI ติดใน nDCG"""
import csv, io, sys
from collections import Counter
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
LAB = ROOT / "eval" / "labels"
DROP = {"a020", "a162", "a074"}

first = {}
for f in ("labels_a.csv", "labels_a2.csv"):
    for r in csv.DictReader((LAB / f).open(encoding="utf-8-sig", newline="")):
        if r["label"].strip().isdigit(): first[r["pair_id"]] = int(r["label"])
chk = [(r["pair_id"], first[r["pair_id"]], int(r["label"]))
       for r in csv.DictReader((LAB / "labels_a_check.csv").open(encoding="utf-8-sig", newline=""))
       if r["pair_id"] in first and r["label"].strip().isdigit()]

def kappa(pairs, k=4, quad=True):
    n = len(pairs)
    if not n: return 0.0
    w = lambda i, j: ((i - j) ** 2 if quad else abs(i - j)) / ((k - 1) ** (2 if quad else 1))
    obs = sum(w(a, b) for _, a, b in pairs) / n
    ca, cb = Counter(a for _, a, _ in pairs), Counter(b for _, _, b in pairs)
    exp = sum(ca[i] * cb[j] / n / n * w(i, j) for i in range(k) for j in range(k))
    return 1 - obs / exp if exp else 0.0

for tag, ps in (("ทั้ง 48 คู่", chk),
                ("ตัด 3 คู่ที่ไม่ปิดตา", [p for p in chk if p[0] not in DROP])):
    ex = sum(1 for _, a, b in ps if a == b)
    print(f"  {tag:24} n={len(ps):>2} · ตรงเป๊ะ {ex}/{len(ps)} ({ex/len(ps)*100:.1f}%) · "
          f"quadratic κ = **{kappa(ps):.3f}** · linear κ = {kappa(ps, quad=False):.3f}")

print("\nทิศทางความต่าง (เฉพาะคู่ที่ไม่ตรงกัน)")
d = Counter()
for _, a, b in chk:
    if a != b: d["คนที่สองให้สูงกว่า" if b > a else "คนที่สองให้ต่ำกว่า"] += 1
for k2, v in d.items(): print(f"  {k2}: {v}")
gap = sum(b - a for _, a, b in chk) / len(chk)
print(f"  ค่าเฉลี่ยส่วนต่าง (คนที่สอง − คนแรก) = **{gap:+.2f} ขั้น**")

# สัดส่วนป้ายที่ AI ติด ในคู่ที่ใช้คิด nDCG รอบ 4
import json
ai = set()
for f in ("labels_a4.csv", "labels_a5.csv", "labels_a6.csv"):
    for r in csv.DictReader((LAB / f).open(encoding="utf-8-sig", newline="")):
        if r["label"].strip().isdigit(): ai.add((r["qid"], r["product_title"]))
hum = set()
for f in ("labels_a.csv", "labels_a2.csv", "labels_a3.csv"):
    for r in csv.DictReader((LAB / f).open(encoding="utf-8-sig", newline="")):
        if r["label"].strip().isdigit(): hum.add((r["qid"], r["product_title"]))
print("\nคู่ที่หยิบมาในรอบ 4 (ไทย) ป้ายมาจากใคร")
for tag, fn in (("ไทย", "collection_th_20261013_1900.json"),
                ("อังกฤษ", "collection_20261013_1329.json")):
    raw = json.loads((Path(r"E:\work\teach\mark7\eval\results") / fn).read_text(encoding="utf-8"))["raw"]
    tot = a = h = 0
    for arm in ("A1_r1", "A3C_r1", "A3_r1"):
        for g in raw[arm]:
            for qid, r in raw[arm][g].items():
                for p in (r.get("picked") or []):
                    tot += 1
                    k3 = (qid, p["title"])
                    if k3 in hum: h += 1
                    elif k3 in ai: a += 1
    print(f"  {tag:8} รวม {tot} คู่ · ผู้วิจัยติด {h} ({h/tot*100:.0f}%) · AI ติด {a} ({a/tot*100:.0f}%)")
