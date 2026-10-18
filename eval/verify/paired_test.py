"""ทดสอบแบบจับคู่ที่ n = 49 — คำนวณ p แบบนับครบทุกกรณีด้วยการกระจายผลรวม (DP)

2^k กรณีที่ k ~ 25 ใหญ่เกินจะวนทีละกรณี แต่ส่วนต่างเป็นจำนวนเต็ม -2..2
จึงคอนโวลูชันการกระจายของผลรวมได้ ผลลัพธ์เท่ากับการนับครบทุกกรณีเป๊ะ
"""
import csv, io, sys
from collections import defaultdict
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
LAB = ROOT / "eval" / "labels"

def load(fn):
    return {r["ans_id"]: int(r["label"])
            for r in csv.DictReader((LAB / fn).open(encoding="utf-8-sig", newline=""))
            if r["label"].strip().isdigit()}

def exact_p(diffs):
    nz = [abs(d) for d in diffs if d != 0]
    obs = abs(sum(d for d in diffs if d != 0))
    if not nz: return 1.0, 0, 0
    dist = {0: 1}
    for d in nz:
        nxt = defaultdict(int)
        for s, c in dist.items():
            nxt[s + d] += c; nxt[s - d] += c
        dist = nxt
    hit = sum(c for s, c in dist.items() if abs(s) >= obs)
    return hit / 2 ** len(nz), len(nz), obs

for tag, a, b in (("รอบ 3 → รอบ 4 · กองเต็ม 49", "labels_b3_th_full.csv", "labels_b4_th_full.csv"),
                  ("รอบ 3 → รอบ 4 · ชุด 15 เดิม", "labels_b3_th.csv", "labels_b4_th.csv")):
    A, B = load(a), load(b)
    ids = sorted(set(A) & set(B))
    diffs = [B[i] - A[i] for i in ids]
    up = sum(1 for d in diffs if d > 0); dn = sum(1 for d in diffs if d < 0)
    p, k, obs = exact_p(diffs)
    sa = sum(A[i] for i in ids) / (2 * len(ids)) * 100
    sb = sum(B[i] for i in ids) / (2 * len(ids)) * 100
    print(f"{tag}")
    print(f"  n={len(ids)} · {sa:.1f}% → {sb:.1f}% (ต่าง {sb-sa:+.1f} จุด)")
    print(f"  ดีขึ้น {up} ข้อ · แย่ลง {dn} ข้อ · เท่าเดิม {len(ids)-up-dn} ข้อ · ป้ายขยับรวม {k} ข้อ")
    print(f"  p = {p:.4f}" + ("  ← แยกจากความบังเอิญได้ (p < 0.05)" if p < 0.05 else "  ← แยกจากความบังเอิญไม่ได้"))
    print()
