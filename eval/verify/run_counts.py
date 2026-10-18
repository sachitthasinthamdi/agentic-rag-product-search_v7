r"""คำนวณทุกตัวเลขที่เล่มอ้างถึง จากไฟล์ผลและไฟล์ป้ายโดยตรง — ไม่พิมพ์มือ ไม่ต้องมีเอกสาร

รัน:  .venv\Scripts\python.exe eval\verify\run_counts.py
เอาผลไปเทียบกับเล่มด้วย eval\verify\check_doc.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter
from math import log2
from pathlib import Path

def _utf8() -> None:
    """บังคับ stdout เป็น utf-8 — เรียกจาก main เท่านั้น
    ถ้าห่อตอน import สคริปต์ที่ import ไฟล์นี้จะเจอ stdout ปิดไปแล้ว"""
    if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "eval" / "labels"
RES = ROOT / "eval" / "results"

RUNS = (("อังกฤษ", "collection_20261013_1329.json"),
        ("ไทย", "collection_th_20261013_1900.json"))
ARMS = ("A1_r1", "A3C_r1", "A3_r1")
IDCG = sum(3 / log2(i + 2) for i in range(3))


def load_a_labels() -> dict[tuple[str, str], int]:
    out = {}
    for f in sorted(LAB.glob("labels_a*.csv")):
        if "check" in f.name or "pilot" in f.name:
            continue
        for r in csv.DictReader(f.open(encoding="utf-8-sig", newline="")):
            if r["label"].strip().isdigit():
                out[(r["qid"], r["product_title"])] = int(r["label"])
    return out


def group_of(name: str) -> str:
    if "g1" in name or "in_domain" in name:
        return "g1"
    return "g3" if ("g3" in name or "out_of" in name) else "g4"


def ndcg(rec: dict, qid: str, lab: dict) -> float:
    gains = [lab.get((qid, p["title"]), 0) for p in (rec.get("picked") or [])[:3]]
    return sum(v / log2(i + 2) for i, v in enumerate(gains)) / IDCG


def b_score(fn: str) -> tuple[int, int, float, Counter]:
    v = [int(r["label"]) for r in csv.DictReader((LAB / fn).open(encoding="utf-8-sig", newline=""))
         if r["label"].strip().isdigit()]
    return sum(v), len(v), sum(v) / (2 * len(v)) * 100, Counter(v)


def main() -> None:
    _utf8()
    lab = load_a_labels()

    print("=" * 78)
    print("  ป้าย ก")
    print("=" * 78)
    tot = 0
    for f in sorted(LAB.glob("labels_a*.csv")):
        if "check" in f.name or "pilot" in f.name:
            continue
        k = sum(1 for r in csv.DictReader(f.open(encoding="utf-8-sig", newline=""))
                if r["label"].strip().isdigit())
        tot += k
        print(f"  {f.name:<24} {k:>4} คู่")
    print(f"  {'รวม':<24} {tot:>4} คู่")

    print()
    print("=" * 78)
    print("  ป้าย ข — ความซื่อตรงของคำตอบ")
    print("=" * 78)
    for fn in sorted(p.name for p in LAB.glob("labels_b*.csv")):
        s, n, pct, c = b_score(fn)
        print(f"  {fn:<26} n={n:>2} · 2={c[2]:>2} 1={c[1]:>2} 0={c[0]:>2} · "
              f"{s}/{2*n} = {pct:5.1f}%")

    for tag, fn in RUNS:
        raw = json.loads((RES / fn).read_text(encoding="utf-8"))["raw"]
        print()
        print("=" * 78)
        print(f"  {tag} · {fn}")
        print("=" * 78)
        for arm in ARMS:
            rows = [r for g in raw[arm] for r in raw[arm][g].values()]
            n = len(rows)
            nd = {group_of(g): round(sum(ndcg(raw[arm][g][q], q, lab)
                                        for q in raw[arm][g]) / len(raw[arm][g]), 3)
                  for g in raw[arm]}
            full = sum(1 for r in rows if len(r.get("picked") or []) == 3)
            loop = sum(1 for r in rows if (r.get("n_searches") or 1) > 1)
            calls = sum(r["llm_calls"] for r in rows)
            secs = sum(r["seconds"] for r in rows)
            g3 = [g for g in raw[arm] if group_of(g) == "g3"][0]
            g1 = [g for g in raw[arm] if group_of(g) == "g1"][0]
            refuse = sum(1 for q in raw[arm][g3] if not (raw[arm][g3][q].get("picked") or []))
            suggest = sum(1 for q in raw[arm][g1] if (raw[arm][g1][q].get("picked") or []))
            bal = (refuse / len(raw[arm][g3]) + suggest / len(raw[arm][g1])) / 2 * 100
            print(f"  {arm[:3]:<4} nDCG g1 {nd['g1']:.3f} · g4 {nd['g4']:.3f} · g3 {nd['g3']:.3f}"
                  f" · ได้ครบ 3 ชิ้น {full}/{n} · ลูปทำงาน {loop/n*100:.0f}%")
            print(f"       ปฏิเสธถูก {refuse}/{len(raw[arm][g3])} ({refuse/len(raw[arm][g3])*100:.1f}%)"
                  f" · แนะนำได้ {suggest}/{len(raw[arm][g1])} · คะแนนตัดสินใจ {bal:.1f}%")
            print(f"       LLM {calls/n:.2f} ครั้ง/ข้อ (รวม {calls}) · "
                  f"เวลา {secs/n:.1f} วิ/ข้อ (รวม {secs/60:.1f} นาที)")
        same = sum(1 for g in raw["A3C_r1"] for q in raw["A3C_r1"][g]
                   if [p["title"] for p in (raw["A3C_r1"][g][q].get("picked") or [])]
                   == [p["title"] for p in (raw["A3_r1"][g][q].get("picked") or [])])
        nq = sum(len(raw["A3C_r1"][g]) for g in raw["A3C_r1"])
        dec = [d for g in raw["A3_r1"] for r in raw["A3_r1"][g].values()
               for d in (r.get("loop_decisions") or [])]
        by_llm = sum(1 for d in dec if d.get("by_llm"))
        print(f"  A3C เทียบ A3 หยิบของเหมือนกัน {same}/{nq} · "
              f"LLM ตัดสินลูปจริง {by_llm}/{len(dec)} "
              f"(ตกไปใช้กฎโค้ด {len(dec)-by_llm} = {(len(dec)-by_llm)/len(dec)*100:.1f}%)")

    print()
    print("=" * 78)
    print("  เทียบสองภาษารวมกัน (A3C กับ A3)")
    print("=" * 78)
    agg = {}
    for arm in ("A3C_r1", "A3_r1"):
        c = s = 0
        for _, fn in RUNS:
            raw = json.loads((RES / fn).read_text(encoding="utf-8"))["raw"]
            c += sum(r["llm_calls"] for g in raw[arm] for r in raw[arm][g].values())
            s += sum(r["seconds"] for g in raw[arm] for r in raw[arm][g].values())
        agg[arm] = (c, s)
        print(f"  {arm[:3]:<4} LLM รวม {c:,} ครั้ง · เวลารวม {s/60:.1f} นาที")
    c1, s1 = agg["A3C_r1"]; c2, s2 = agg["A3_r1"]
    print(f"  A3 แพงกว่า A3C: LLM +{(c2/c1-1)*100:.0f}% · เวลา +{(s2/s1-1)*100:.0f}%")


if __name__ == "__main__":
    main()
