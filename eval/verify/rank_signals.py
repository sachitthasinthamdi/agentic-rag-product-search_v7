"""ชั้นจัดอันดับ — วัดว่าสัญญาณไหนช่วย โดยไม่ติด pooling bias

**ปัญหาที่สคริปต์นี้แก้:** ถ้าเปลี่ยนวิธีจัดอันดับแล้ววัดบนกองเดิม
ของที่ไม่เคยติดป้าย (เพราะระบบเดิมไม่เคยหยิบ) จะโผล่ขึ้นมาแล้วถูกนับเป็น 0
ทำให้วิธีใหม่ดูแย่เสมอ (Zobel 1998)

**วิธีแก้:** จำกัดผู้เข้าชิงให้เหลือ**เฉพาะสินค้าที่มีป้ายสำหรับคำค้นนั้น**
ทุกชิ้นจึงมีป้าย ไม่มีของใหม่โผล่มา → เทียบวิธีจัดอันดับได้อย่างเป็นธรรม

⚠ ตัวเลขที่ได้**ไม่ใช่ค่าปลายทางจริง** เป็นค่าบนกองที่จำกัดแล้ว
ใช้เทียบ "วิธี ก กับ วิธี ข" เท่านั้น ห้ามเอาไปรายงานเป็น nDCG ของระบบ

⚠ เลือกค่าที่ดีที่สุดจากชุดนี้ = **ปรับจูนบนชุดทดสอบ** ต้องเขียนเป็นข้อจำกัด

รัน:  python eval\verify\rank_signals.py
"""
from __future__ import annotations

import csv, io, json, sys
from math import log2
from pathlib import Path
from collections import defaultdict
from statistics import mean

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval.collection import GROUP1_IN_DOMAIN, GROUP4_BUDGET      # noqa: E402
from eval.collection_th import GROUP1_TH, GROUP4_TH              # noqa: E402
from src.rerank import apply_gate, order_by_votes            # noqa: E402
from src.retrieval import Retriever                              # noqa: E402

K, IDCG = 3, sum(3 / log2(i + 1) for i in range(1, 4))

# คำค้นภาษาไทยใช้ "คำค้นที่แปลแล้ว" จากบันทึกการรันจริง จะได้ไม่ต้องเรียกโมเดลซ้ำ
TH_LOG = ROOT / "eval/results/collection_th_20261013_1900.json"


def load_labels() -> dict[tuple[str, str], int]:
    """{(qid, 40 ตัวแรกของชื่อสินค้า): ป้าย} — ไฟล์ป้ายไม่มีรหัสสินค้า จับคู่ด้วยชื่อ
    ที่ตัด 40 ตัวเพราะบางไฟล์เก็บชื่อแบบตัดสั้น"""
    out: dict[tuple[str, str], int] = {}
    for path in sorted((ROOT / "eval/labels").glob("labels_a*.csv")):
        if path.name.endswith(("_check.csv", "_pilot.csv")):
            continue
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["label"].strip().isdigit():
                    out[(r["qid"], r["product_title"][:40])] = int(r["label"])
    return out


def ndcg(hits, qid, lab) -> float:
    gains = [lab.get((qid, h.title[:40]), 0) for h in hits[:K]]
    gains += [0] * (K - len(gains))
    return sum(g / log2(i + 1) for i, g in enumerate(gains, 1)) / IDCG


# ค่าที่จะลอง: (ชื่อ, ตรง, ดาว, รีวิว, หมวด, คำซ้อน)
CONFIGS = [
    ("ของเดิม 3:1:1:1 ไม่มีคำซ้อน",      3, 1, 1, 1, 0),
    ("+ คำซ้อน 1  (คงรีวิว)",            3, 1, 1, 1, 1),
    ("+ คำซ้อน 3  (คงรีวิว)",            3, 1, 1, 1, 3),
    ("+ คำซ้อน 6  (คงรีวิว)",            3, 1, 1, 1, 6),
    ("ตรง 3 + คำซ้อน 3 ไม่เอารีวิว",      3, 1, 0, 1, 3),
    ("ตรง 3 + คำซ้อน 6 ไม่เอารีวิว",      3, 1, 0, 1, 6),
    ("คำซ้อนล้วน",                        0, 0, 0, 0, 1),
]


def rank_with_words(hits, w_rel, w_rat, w_rev, w_cat, w_words, search_text):
    """เรียกตัวจัดอันดับ**ตัวจริง** ใน src/rerank.py — ไม่ทำสำเนาสูตรไว้ที่นี่
    ไม่งั้นค่าที่วัดได้จะไม่ใช่ค่าที่ระบบใช้จริง"""
    ranked = order_by_votes(hits, w_relevance=w_rel, w_rating=w_rat,
                            w_reviews=w_rev, w_category=w_cat,
                            w_words=w_words, search_text=search_text)
    return [r.hit for r in ranked]


def exact_p(diffs: list[float]) -> float:
    """ทดสอบสลับเครื่องหมายแบบนับครบทุกกรณี — รวมการแจกแจงด้วย DP
    (2^k ตรง ๆ ไม่ไหวที่ k หลายสิบ)

    ⚠ **ปัดค่าต่างเป็นจำนวนเต็มก่อน แล้วค่อยบวก** ห้ามปัดผลรวม —
    เคยเขียนเป็น `round(sum(...))` แล้วค่าที่สังเกตได้เกินค่าสูงสุดที่การแจกแจง
    ทำได้ 1 หน่วย ตัวเศษจึงเป็น 0 และคืน p = 0.0 ทั้งที่ค่าต่ำสุดที่เป็นไปได้
    คือ 2 / 2^k (เจอ 16 ต.ค. 2026 ตอนผลไทยให้ p = 0.0000 ที่ k = 3)
    """
    vals = [round(d * 1e4) for d in diffs if abs(d) > 1e-9]
    vals = [v for v in vals if v != 0]
    if not vals:
        return 1.0
    obs = abs(sum(vals))
    dist = {0: 1}
    for v in vals:
        nxt = defaultdict(int)
        for s, c in dist.items():
            nxt[s + abs(v)] += c
            nxt[s - abs(v)] += c
        dist = nxt
    return sum(c for s, c in dist.items() if abs(s) >= obs) / 2 ** len(vals)


def pick_diverse_hits(ordered):
    """ชั้น 4 ย่อ — หยิบ K ชิ้น ห้ามร้านซ้ำ แล้วเติมของที่ร้านซ้ำถ้าไม่พอ"""
    picked, seen, skipped = [], set(), []
    for h in ordered:
        if h.store is not None and h.store in seen:
            skipped.append(h)
            continue
        picked.append(h)
        if h.store is not None:
            seen.add(h.store)
        if len(picked) == K:
            return picked
    return (picked + skipped)[:K]


def main() -> None:
    lab = load_labels()
    th_log = json.loads(TH_LOG.read_text(encoding="utf-8"))["raw"]["A3C_r1"]

    # (ภาษา, [(qid, คำค้นที่ใช้ค้นจริง)])
    en = ([(x["id"], x["q"]) for x in GROUP1_IN_DOMAIN]
          + [(x["id"], x["q"]) for x in GROUP4_BUDGET])
    th = []
    for grp, table in (("g1", GROUP1_TH), ("g4", GROUP4_TH)):
        for qid in table:
            st = (th_log.get(grp, {}).get(qid, {}).get("search_texts") or [None])[0]
            if st:
                th.append((qid, st))

    with Retriever() as r:
        for langname, pairs in (("ไทย (ค้นด้วยคำแปลจากบันทึกการรันจริง)", th),
                                ("อังกฤษ", en)):
            rows: dict[str, list[float]] = {c[0]: [] for c in CONFIGS}
            used = 0
            for qid, text in pairs:
                hits = r.search(text, k=100)
                # จำกัดเฉพาะของที่มีป้ายแล้ว -> ไม่มีของใหม่โผล่มาให้นับเป็น 0
                hits = [h for h in apply_gate(hits, 0.55) if (qid, h.title[:40]) in lab]
                if len(hits) < K:
                    continue
                used += 1
                for name, a, b, c, d, w in CONFIGS:
                    ordered = rank_with_words(hits, a, b, c, d, w, text)
                    rows[name].append(ndcg(pick_diverse_hits(ordered), qid, lab))

            b0 = rows[CONFIGS[0][0]]
            base = mean(b0)
            print(f"\n===== {langname} · {used} คำค้นที่มีของติดป้าย >= {K} ชิ้น")
            for name, *_ in CONFIGS:
                col = rows[name]
                v = mean(col)
                dd = [x - y for x, y in zip(col, b0)]
                up = sum(1 for x in dd if x > 1e-9)
                dn = sum(1 for x in dd if x < -1e-9)
                pv = exact_p(dd)
                tag = "" if name == CONFIGS[0][0] else (
                    f"  ดีขึ้น {up:2d} · แย่ลง {dn:2d} · p = {pv:.4f}"
                    + ("  ← มีนัยสำคัญ" if pv < 0.05 else ""))
                print(f"   {name:<34} nDCG@3 = {v:.4f}  ({(v-base)*100:+.1f} จุด){tag}")


if __name__ == "__main__":
    main()
