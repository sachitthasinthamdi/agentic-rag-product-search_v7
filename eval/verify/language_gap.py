r"""ช่องว่างระหว่างภาษาในป้าย ข — ทดสอบแบบจับคู่ตามคำค้น

คำค้นฝั่งไทยเป็นคำแปลของคำค้นฝั่งอังกฤษชุดเดียวกัน จึงจับคู่ตาม qid ได้
แข็งกว่าการเทียบค่าเฉลี่ย เพราะบอกได้ว่าส่วนต่างมาจากคำค้นกี่คำ

รัน:  .venv\Scripts\python.exe eval\verify\language_gap.py
"""
import csv
import io
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "eval" / "labels"


def load(fn: str) -> dict[str, int]:
    return {r["qid"]: int(r["label"])
            for r in csv.DictReader((LAB / fn).open(encoding="utf-8-sig", newline=""))
            if r["label"].strip().isdigit()}


def exact_p(diffs: list[int]) -> tuple[float, int]:
    nz = [abs(d) for d in diffs if d]
    obs = abs(sum(d for d in diffs if d))
    if not nz:
        return 1.0, 0
    dist = {0: 1}
    for d in nz:
        nxt: dict[int, int] = defaultdict(int)
        for s, c in dist.items():
            nxt[s + d] += c
            nxt[s - d] += c
        dist = nxt
    return sum(c for s, c in dist.items() if abs(s) >= obs) / 2 ** len(nz), len(nz)


def main() -> None:
    if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    en = load("labels_b3_full.csv")
    pairs = (("ไทย รอบ 3 (พรอมต์เดิม)", "labels_b3_th_full.csv"),
             ("ไทย รอบ 4 (หลังแก้พรอมต์ไทย)", "labels_b4_th_full.csv"),
             ("ไทย รอบ 4 แขน A1", "labels_b4_th_a1.csv"))
    sc = lambda d, ids: sum(d[i] for i in ids) / (2 * len(ids)) * 100
    print(f"อังกฤษ รอบ 3 กองเต็ม n={len(en)} · {sc(en, list(en))::.1f}%" if False else
          f"อังกฤษ รอบ 3 กองเต็ม n={len(en)} · {sc(en, list(en)):.1f}%")
    for tag, fn in pairs:
        th = load(fn)
        ids = sorted(set(en) & set(th))
        diffs = [en[i] - th[i] for i in ids]
        up = sum(1 for d in diffs if d > 0)
        dn = sum(1 for d in diffs if d < 0)
        p, k = exact_p(diffs)
        e, t = sc(en, ids), sc(th, ids)
        print()
        print(f"{tag}  (จับคู่ {len(ids)} คำค้น)")
        print(f"  อังกฤษ {e:.1f}% · ไทย {t:.1f}% · ช่องว่าง {e-t:+.1f} จุด = {e/t:.2f} เท่า")
        print(f"  อังกฤษดีกว่า {up} คำ · ไทยดีกว่า {dn} คำ · เท่ากัน {len(ids)-up-dn} คำ")
        print(f"  p = {p:.6f}" + ("  ← มีนัยสำคัญ" if p < 0.05 else "  ← แยกจากความบังเอิญไม่ได้"))


if __name__ == "__main__":
    main()
