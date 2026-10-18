"""วัดความสอดคล้องระหว่างคนติดป้าย 2 คน — weighted kappa

⚠ **ต้องใช้ weighted kappa ไม่ใช่ kappa ธรรมดา** (Cohen 1968)
ป้ายของเราเป็น**ลำดับ** 3 > 2 > 1 > 0 ไม่ใช่หมวดหมู่ที่ไม่เกี่ยวกัน
การที่คนหนึ่งให้ 3 อีกคนให้ 2 ควรถูกหักน้อยกว่าการที่อีกคนให้ 0
kappa ธรรมดาหักเท่ากันหมด ซึ่งประเมินความสอดคล้องต่ำกว่าความจริง

รายงานทั้ง 2 แบบของน้ำหนัก
  linear     โทษตามระยะห่าง         |i-j| / (k-1)
  quadratic  โทษความต่างมาก ๆ หนักขึ้น  (i-j)^2 / (k-1)^2   <- ใช้กันบ่อยกว่า

เกณฑ์แปลผล Landis & Koch (1977) · **เกณฑ์ผ่านของโปรเจกต์นี้คือ 0.60**
ถ้าต่ำกว่า 0.60 **ห้ามรายงาน nDCG เป็นค่าสัมบูรณ์** (ดู docs/eval_plan.md ข้อ 5)

รัน:  python eval\\kappa.py eval\\labels\\labels_a_check.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "eval" / "labels"
SOURCES = [LAB / "labels_a.csv", LAB / "labels_a2.csv"]
LEVELS = [0, 1, 2, 3]
BANDS = [(0.81, "ดีมาก"), (0.61, "ดี  <- ผ่านเกณฑ์โปรเจกต์"),
         (0.41, "พอใช้"), (0.21, "น้อย"), (-1.0, "แทบไม่สอดคล้อง")]


def read_labels(path: Path) -> dict[str, int]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {r["pair_id"]: int(r["label"]) for r in csv.DictReader(fh)
                if r["label"].strip()}


def kappa(a: list[int], b: list[int], weight: str) -> float:
    """weighted kappa · weight = 'linear' | 'quadratic' | 'none'"""
    k, n = len(LEVELS), len(a)
    idx = {v: i for i, v in enumerate(LEVELS)}
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1 / n
    ma = [sum(obs[i]) for i in range(k)]
    mb = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def w(i: int, j: int) -> float:
        d = abs(i - j)
        if weight == "none":
            return 0.0 if d else 1.0
        if weight == "linear":
            return 1 - d / (k - 1)
        return 1 - (d / (k - 1)) ** 2

    po = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    pe = sum(w(i, j) * ma[i] * mb[j] for i in range(k) for j in range(k))
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def band(v: float) -> str:
    return next(name for lo, name in BANDS if v >= lo)


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="วัดความสอดคล้องของป้าย 2 คน")
    ap.add_argument("check", type=Path, help="ไฟล์ที่คนที่สองติดแล้ว")
    # ⚠ ต้องชี้กองของคนแรกได้ — กองที่ Claude ติดอยู่ใน `labels_a4.csv`
    # ถ้าใช้ค่าตั้งต้น (labels_a.csv + labels_a2.csv) จะไม่เจอ pair_id เลย
    ap.add_argument("--from", dest="srcs", nargs="+", type=Path, default=None,
                    help="ไฟล์ป้ายของคนแรก (ไม่ระบุ = labels_a.csv + labels_a2.csv)")
    args = ap.parse_args()

    sources = [LAB / s.name if s.parent == Path(".") else s
               for s in (args.srcs or SOURCES)]
    first: dict[str, int] = {}
    for s in sources:
        if s.exists():
            first.update(read_labels(s))
    second = read_labels(args.check)
    both = sorted(set(first) & set(second))
    if not both:
        raise SystemExit("❌ ไม่มี pair_id ที่ตรงกัน — คนที่สองยังไม่ได้กรอกป้ายใช่ไหม")
    missing = len(second) - len(both)

    a = [first[p] for p in both]
    b = [second[p] for p in both]
    exact = sum(1 for x, y in zip(a, b) if x == y)
    near = sum(1 for x, y in zip(a, b) if abs(x - y) <= 1)

    print(f"เทียบได้ {len(both)} คู่" + (f" (ข้ามไป {missing} เพราะหาคู่ไม่เจอ)" if missing else ""))
    print(f"\nตรงกันเป๊ะ        {exact}/{len(both)} ({exact / len(both) * 100:.1f}%)")
    print(f"ต่างกันไม่เกิน 1  {near}/{len(both)} ({near / len(both) * 100:.1f}%)")

    print(f"\n{'แบบน้ำหนัก':<16}{'kappa':>8}   แปลผล (Landis & Koch 1977)")
    print("-" * 62)
    for wname, label in (("quadratic", "quadratic <- ตัวหลัก"), ("linear", "linear"),
                         ("none", "ไม่ถ่วง (อ้างอิง)")):
        v = kappa(a, b, wname)
        print(f"{label:<16}{v:>8.3f}   {band(v)}")

    print(f"\nตารางความต่าง (แถว = คนแรก · คอลัมน์ = คนที่สอง)")
    print("        " + "".join(f"{v:>6}" for v in LEVELS))
    cnt = Counter(zip(a, b))
    for i in LEVELS:
        row = "".join(f"{cnt.get((i, j), 0):>6}" for j in LEVELS)
        print(f"  {i:<6}{row}")

    worst = sorted(((abs(x - y), p, x, y) for p, x, y in zip(both, a, b)),
                   reverse=True)[:8]
    bad = [w for w in worst if w[0] >= 2]
    if bad:
        print(f"\nคู่ที่ต่างกันตั้งแต่ 2 ขั้นขึ้นไป ({len(bad)} คู่แรก) — ควรมานั่งดูด้วยกัน")
        for d, p, x, y in bad:
            print(f"  {p}  คนแรก {x} · คนที่สอง {y}  (ต่าง {d})")

    q = kappa(a, b, "quadratic")
    print()
    if q >= 0.61:
        print(f"✅ quadratic kappa = {q:.3f} >= 0.60 — รายงาน nDCG เป็นค่าสัมบูรณ์ได้")
    else:
        print(f"⚠ quadratic kappa = {q:.3f} < 0.60 — **ห้ามรายงาน nDCG เป็นค่าสัมบูรณ์**")
        print("   ต้องรายงานเป็นการเทียบอันดับแทน และแก้คู่มือติดป้ายก่อนติดเพิ่ม")


if __name__ == "__main__":
    main()
