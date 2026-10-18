"""ตัวชี้วัดที่ต้องใช้ป้ายจากคน — nDCG@3 · P@3 · การกระจายของป้าย

คู่กับ `eval/metrics.py` ซึ่งคิดเฉพาะส่วนที่ไม่ต้องใช้ป้าย

⚠ **ตัวหารของ nDCG ใช้ระบบในอุดมคติ ไม่ใช่กองป้าย**
กองป้ายของเรามาจากระบบเดียว (A3) ถ้าใช้ "อันดับที่ดีที่สุดเท่าที่มีในกอง"
เป็นตัวหาร ระบบที่หยิบของห่วย 3 ชิ้นจะได้ nDCG = 1.00 เพราะของดีที่สุดในกอง
ก็คือของห่วยนั้นเอง -> ไร้ความหมาย
จึงตั้งตัวหารเป็น [3, 3, 3] คือ "ถ้าระบบสมบูรณ์แบบจะคืนของตรงเป๊ะครบ 3 ชิ้น"
ตัวเลขที่ได้จึงอ่านว่า **ระบบทำได้กี่ % ของระบบที่สมบูรณ์แบบ**
(ถ้าภายหลังมีหลายระบบและ pooling ครบ ค่อยเปลี่ยนมาใช้ตัวหารแบบ TREC ปกติ)

⚠ **ค่าน้ำหนักของป้าย** ใช้แบบเชิงเส้น 3/2/1/0 ตาม Järvelin & Kekäläinen (2002)
ไม่ใช้ 2^rel-1 เพราะจะถ่วงให้ "ตรงเป๊ะ" สำคัญกว่า "ใช้แทนได้" มากเกินจริง
สำหรับงานแนะนำสินค้าที่ของใช้แทนกันได้มีค่าจริงกับผู้ใช้

รัน:  python eval\\metrics_labelled.py eval\\results\\collection_20261003_2039.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from math import log2
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.collection import (GROUP1_IN_DOMAIN, GROUP3_OUT_OF_DOMAIN,  # noqa: E402
                             GROUP4_BUDGET)

# ⚠ อ่านป้ายจากทุกไฟล์ — `labels_a2.csv` คือส่วนที่ติดเพิ่มหลังรอบภาษาไทย
# (ระบบหยิบของคนละชุดราวครึ่งหนึ่ง กองเดิมจึงไม่ครอบคลุม)
LABEL_FILES = sorted(
    f for f in (ROOT / "eval" / "labels").glob("labels_a*.csv")
    if not f.name.endswith(("_check.csv", "_pilot.csv")))
K = 3
PERFECT = [3] * K            # ระบบในอุดมคติ: ตรงเป๊ะครบ 3 ชิ้น
# ⚠ ต้องครบ 3 กลุ่ม — เดิมคิดแค่ g1 ทำให้ทุกแขนได้เลขเท่ากันเสมอ
# เพราะลูปของ A3/A3C ไม่เคยยิงในกลุ่ม g1 (คลังมีของเหลือเฟือ)
GROUPS = {"g1": GROUP1_IN_DOMAIN, "g3": GROUP3_OUT_OF_DOMAIN,
          "g4": GROUP4_BUDGET}
BAND = {x["id"]: x.get("band", "—") for items in GROUPS.values() for x in items}


def load_labels() -> dict[tuple[str, str], int]:
    """คืน {(qid, ชื่อสินค้า): ป้าย} — ไฟล์ป้ายไม่มีรหัสสินค้า จึงจับคู่ด้วยชื่อ"""
    out = {}
    for path in LABEL_FILES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["label"].strip():
                    out[(r["qid"], r["product_title"])] = int(r["label"])
    return out


def dcg(gains: list[int]) -> float:
    return sum(g / log2(i + 1) for i, g in enumerate(gains, 1))


IDCG = dcg(PERFECT)


def per_query(rec: dict, qid: str, lab: dict) -> dict | None:
    """คิดตัวชี้วัดของคำค้นเดียว · คืน None ถ้าหาป้ายไม่ครบ"""
    gains = []
    for p in rec["picked"][:K]:
        g = lab.get((qid, p["title"]))
        if g is None:
            return None
        gains.append(g)
    n_short = K - len(gains)          # หยิบมาไม่ครบ 3 -> เติม 0 (ผู้ใช้ไม่ได้เห็นอะไร)
    gains += [0] * n_short
    return {"gains": gains,
            "ndcg": dcg(gains) / IDCG,
            "p_at3_rel": sum(1 for g in gains if g >= 2) / K,
            "p_at3_exact": sum(1 for g in gains if g == 3) / K,
            "mean_label": mean(gains),
            "any_exact": int(any(g == 3 for g in gains)),
            "all_irrelevant": int(all(g == 0 for g in gains)),
            "short": n_short}


def run(raw: dict, lab: dict, group: str = "g1") -> dict:
    out: dict[str, dict] = {}
    for key in sorted(raw):
        items = raw[key].get(group, {})
        rows, unjudged = {}, 0
        for qid, rec in items.items():
            r = per_query(rec, qid, lab)
            if r is None:
                unjudged += 1
            else:
                rows[qid] = r
        out[key] = {"rows": rows, "n": len(rows), "unjudged": unjudged}
    return out


def agg(rows: dict) -> dict:
    v = list(rows.values())
    return {f: mean(r[f] for r in v) for f in
            ("ndcg", "p_at3_rel", "p_at3_exact", "mean_label",
             "any_exact", "all_irrelevant")}


def report(res: dict, title: str = "") -> None:
    bar = "=" * 76
    print(f"\n{bar}\n  ตัวชี้วัดที่ใช้ป้าย — {title or 'กลุ่ม 1 (คลังมีของ)'}\n{bar}")
    print(f"  ตัวหาร nDCG = ระบบในอุดมคติ [3,3,3] · DCG สูงสุด = {IDCG:.4f}\n")

    hdr = f"  {'':<10}{'nDCG@3':>9}{'P@3 ตรง/แทน':>14}{'P@3 ตรงเป๊ะ':>13}" \
          f"{'ป้ายเฉลี่ย':>12}{'มีของตรง':>11}{'ห่วยหมด':>10}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    per_round = {}
    for key, d in res.items():
        # ⚠ ไฟล์ผลที่รันค้างกลางทางจะมีแขนที่ไม่มีแถวในกลุ่มนี้เลย
        # ต้อง**ข้าม** ไม่ใช่ล้มทั้งรายงาน (เจอ 2026-10-13 ตอน A3_r2 ค้าง 26 ข้อ)
        if not d["rows"]:
            print(f"  {key:<10}      — ข้าม ไม่มีคำค้นในกลุ่มนี้ (รันค้าง)")
            continue
        a = agg(d["rows"])
        per_round[key] = a
        print(f"  {key:<10}{a['ndcg']:>9.3f}{a['p_at3_rel'] * 100:>13.1f}%"
              f"{a['p_at3_exact'] * 100:>12.1f}%{a['mean_label']:>12.2f}"
              f"{a['any_exact'] * 100:>10.1f}%{a['all_irrelevant'] * 100:>9.1f}%")
        if d["unjudged"]:
            print(f"      ⚠ หาป้ายไม่ครบ {d['unjudged']} คำค้น")
    if len(per_round) > 1:
        print("  " + "-" * (len(hdr) - 2))
        m = {f: mean(a[f] for a in per_round.values()) for f in
             ("ndcg", "p_at3_rel", "p_at3_exact", "mean_label",
              "any_exact", "all_irrelevant")}
        rng = max(a["ndcg"] for a in per_round.values()) - \
            min(a["ndcg"] for a in per_round.values())
        print(f"  {'เฉลี่ย':<10}{m['ndcg']:>9.3f}{m['p_at3_rel'] * 100:>13.1f}%"
              f"{m['p_at3_exact'] * 100:>12.1f}%{m['mean_label']:>12.2f}"
              f"{m['any_exact'] * 100:>10.1f}%{m['all_irrelevant'] * 100:>9.1f}%")
        print(f"\n  ช่วงแกว่งของ nDCG ข้ามรอบ: {rng:.3f}")

    # แยกตามชั้นความยาก — ใช้รอบแรกเป็นตัวแทน
    first = res[sorted(res)[0]]["rows"]
    print(f"\n{'-' * 76}\n  แยกตามชั้นความยากของคำค้น (รอบแรก)\n{'-' * 76}")
    print(f"  {'ชั้น':<10}{'จำนวน':>7}{'nDCG@3':>10}{'P@3 ตรง/แทน':>15}{'ห่วยหมด':>11}")
    for band in ("ง่าย", "กลาง", "ยาก"):
        v = [r for q, r in first.items() if BAND.get(q) == band]
        if not v:
            continue
        print(f"  {band:<10}{len(v):>7}{mean(r['ndcg'] for r in v):>10.3f}"
              f"{mean(r['p_at3_rel'] for r in v) * 100:>14.1f}%"
              f"{mean(r['all_irrelevant'] for r in v) * 100:>10.1f}%")

    # คำค้นที่แย่ที่สุด — ไว้ไปวิเคราะห์ต่อ
    worst = sorted(first.items(), key=lambda kv: kv[1]["ndcg"])[:8]
    qtext = {x["id"]: x["q"] for its in GROUPS.values() for x in its}
    print(f"\n{'-' * 76}\n  8 คำค้นที่ระบบทำได้แย่ที่สุด (รอบแรก)\n{'-' * 76}")
    for qid, r in worst:
        print(f"  {r['ndcg']:>5.3f}  ป้าย {r['gains']}  [{BAND.get(qid, '—')}]  "
              f"{qtext.get(qid, qid)[:46]}")


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="ตัวชี้วัดที่ใช้ป้าย")
    ap.add_argument("results", type=Path)
    ap.add_argument("--group", choices=["g1", "g3", "g4", "all"], default="all")
    args = ap.parse_args()

    lab = load_labels()
    print(f"อ่านป้าย {len(lab)} คู่ จาก " + " + ".join(f.name for f in LABEL_FILES if f.exists()))
    raw = json.loads(args.results.read_text(encoding="utf-8"))["raw"]
    want = list(GROUPS) if args.group == "all" else [args.group]
    for g in want:
        name = {"g1": "กลุ่ม 1 (คลังมีของ)", "g3": "กลุ่ม 3 (นอกคลัง)",
                "g4": "กลุ่ม 4 (มีงบ)"}[g]
        bar = "#" * 76
        print(f"\n\n{bar}\n#  {name}\n{bar}")
        if g == "g3":
            print("  ⚠ nDCG ของกลุ่มนี้อ่านอย่างระวัง — คำตอบที่ถูกของบางคำคือ"
                  ' "ไม่พบ" ซึ่ง nDCG ให้ 0 เท่ากับการหยิบของผิด')
        report(run(raw, lab, g), name)


if __name__ == "__main__":
    main()
