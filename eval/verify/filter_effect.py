"""ฉากถอดตัวกรองออกที่ n = 49 — แยกผลของพรอมต์ V3 ออกจากผลของตัวกรอง

ข้อที่ echoed=[1,2,3] คือทุกบรรทัดถูกตัวกรองทิ้ง ถ้าไม่มีตัวกรองคำตอบจะเป็น
การลอกคำค้นมาวางทั้ง 3 ชิ้น ซึ่งรอบ 3 ติดป้ายคำค้นเดียวกันนี้ได้ 0 ทุกข้อ
จึงใช้ 0 เป็นป้ายฉากถอดตัวกรอง
"""
import csv, io, json, sys
from collections import defaultdict
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
def load(fn):
    return {r["ans_id"]: int(r["label"])
            for r in csv.DictReader((ROOT / "eval/labels" / fn).open(encoding="utf-8-sig", newline=""))
            if r["label"].strip().isdigit()}

def exact_p(diffs):
    nz = [abs(d) for d in diffs if d != 0]
    obs = abs(sum(d for d in diffs if d != 0))
    if not nz: return 1.0, 0
    dist = {0: 1}
    for d in nz:
        nxt = defaultdict(int)
        for s, c in dist.items(): nxt[s + d] += c; nxt[s - d] += c
        dist = nxt
    return sum(c for s, c in dist.items() if abs(s) >= obs) / 2 ** len(nz), len(nz)

raw = json.loads((ROOT / "eval/results/collection_th_20261013_1900.json").read_text(encoding="utf-8"))["raw"]["A3_r1"]["g1"]
qid2ans = {r["qid"]: r["ans_id"] for r in
           csv.DictReader((ROOT / "eval/labels/labels_b4_th_full.csv").open(encoding="utf-8-sig", newline=""))}
allech = [qid2ans[q] for q, r in raw.items() if (r.get("echoed") or []) == [1, 2, 3] and q in qid2ans]

r3, r4 = load("labels_b3_th_full.csv"), load("labels_b4_th_full.csv")
nf = dict(r4)
for a in allech: nf[a] = 0          # ฉากถอดตัวกรอง
ids = sorted(set(r3) & set(r4))
sc = lambda d: sum(d[i] for i in ids) / (2 * len(ids)) * 100

print(f"ข้อที่ตัวกรองทิ้งทุกบรรทัด {len(allech)} ข้อ: {' '.join(sorted(allech))}\n")
print(f"  รอบ 3 พรอมต์เดิม ไม่มีตัวกรอง      {sc(r3):5.1f}%")
print(f"  รอบ 4 พรอมต์ V3 ถ้าถอดตัวกรองออก   {sc(nf):5.1f}%   (ผลของพรอมต์เพียว ๆ {sc(nf)-sc(r3):+.1f} จุด)")
print(f"  รอบ 4 จริง พรอมต์ V3 + ตัวกรอง      {sc(r4):5.1f}%   (ผลของตัวกรอง {sc(r4)-sc(nf):+.1f} จุด)\n")
for tag, a, b in (("พรอมต์เพียว ๆ (รอบ 3 → ฉากถอดตัวกรอง)", r3, nf),
                  ("ตัวกรอง (ฉากถอดตัวกรอง → รอบ 4 จริง)", nf, r4),
                  ("รวมทั้งสองอย่าง (รอบ 3 → รอบ 4 จริง)", r3, r4)):
    diffs = [b[i] - a[i] for i in ids]
    p, k = exact_p(diffs)
    up = sum(1 for d in diffs if d > 0); dn = sum(1 for d in diffs if d < 0)
    print(f"  {tag}")
    print(f"    ดีขึ้น {up} · แย่ลง {dn} · เท่าเดิม {len(ids)-up-dn} · p = {p:.4f}"
          + ("  ← มีนัยสำคัญ" if p < 0.05 else "  ← แยกจากความบังเอิญไม่ได้"))
