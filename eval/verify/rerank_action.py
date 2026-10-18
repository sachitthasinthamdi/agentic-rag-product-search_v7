"""ขั้นที่ 2 — วัด action ใหม่ "จัดอันดับกองเดิมใหม่ด้วยน้ำหนักคำซ้อนสูง"

ลูปเห็นว่าของครบแต่ชื่อสินค้าไม่มีคำที่ผู้ใช้ขอ (word_match ต่ำ) แล้ว**ลงมือ
จัดอันดับกองเดิมใหม่** โดยไม่ต้องค้นซ้ำ ไม่ต้องเรียก LLM

สคริปต์นี้ตอบว่า: ยิงกี่ข้อ · ยิงแล้วดีขึ้นจริงไหม · น้ำหนักเท่าไรดีที่สุด

⚠ จำกัดผู้เข้าชิงเฉพาะของมีป้าย เหมือน `rank_signals.py` (กัน pooling bias)

รัน:  python evalerify
erank_action.py
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
from src.rerank import (apply_gate, order_by_votes,           # noqa: E402
                        word_overlap)
from src.retrieval import Retriever                              # noqa: E402
from eval.verify.rank_signals import exact_p                     # noqa: E402

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


WORD_MATCH = 0.34            # เกณฑ์เดียวกับ src/a3.py
BOOSTS = [6, 12, 20, 40, 100]


def word_match_top(search_text, titles):
    """มัธยฐานสัดส่วนคำที่ซ้อน — ยกมาจาก src/a3.py ให้เกณฑ์ยิงตรงกัน"""
    if not titles:
        return 1.0
    v = sorted(word_overlap(search_text, t) for t in titles)
    return v[len(v) // 2] if len(v) % 2 else (v[len(v)//2 - 1] + v[len(v)//2]) / 2


def pick_diverse_hits(ordered):
    picked, seen, skipped = [], set(), []
    for h in ordered:
        if h.store is not None and h.store in seen:
            skipped.append(h); continue
        picked.append(h)
        if h.store is not None:
            seen.add(h.store)
        if len(picked) == K:
            return picked
    return (picked + skipped)[:K]


def top(hits, w_words, search_text):
    r = order_by_votes(hits, w_words=w_words, search_text=search_text)
    return pick_diverse_hits([x.hit for x in r])


def main():
    lab = load_labels()
    th_log = json.loads(TH_LOG.read_text(encoding="utf-8"))["raw"]["A3C_r1"]
    en = ([(x["id"], x["q"]) for x in GROUP1_IN_DOMAIN]
          + [(x["id"], x["q"]) for x in GROUP4_BUDGET])
    th = []
    for grp, table in (("g1", GROUP1_TH), ("g4", GROUP4_TH)):
        for qid in table:
            st = (th_log.get(grp, {}).get(qid, {}).get("search_texts") or [None])[0]
            if st:
                th.append((qid, st))

    with Retriever() as r:
        for langname, pairs in (("ไทย", th), ("อังกฤษ", en)):
            fired, base, after = [], [], {b: [] for b in BOOSTS}
            allbase, allafter = [], {b: [] for b in BOOSTS}
            for qid, text in pairs:
                hits = [h for h in apply_gate(r.search(text, k=100), 0.55)
                        if (qid, h.title[:40]) in lab]
                if len(hits) < K:
                    continue
                p0 = top(hits, 6, text)
                n0 = ndcg(p0, qid, lab)
                allbase.append(n0)
                wm = word_match_top(text, [h.title for h in p0])
                hit_rule = wm < WORD_MATCH
                for b in BOOSTS:
                    nb = ndcg(top(hits, b, text), qid, lab) if hit_rule else n0
                    allafter[b].append(nb)
                    if hit_rule:
                        after[b].append(nb)
                if hit_rule:
                    fired.append(qid); base.append(n0)

            print(f"\n===== {langname} · {len(allbase)} คำค้น · "
                  f"กฎยิง {len(fired)} ข้อ ({len(fired)/max(1,len(allbase)):.0%})")
            if not fired:
                print("   กฎไม่ยิงเลย"); continue
            print(f"   {'น้ำหนักตอนยิง':<16}{'เฉพาะข้อที่ยิง':>16}{'ทั้งชุด':>14}   นัยสำคัญทั้งชุด")
            print(f"   {'ไม่ทำอะไร (6)':<16}{sum(base)/len(base):>16.4f}"
                  f"{sum(allbase)/len(allbase):>14.4f}")
            for b in BOOSTS[1:]:
                m, ma = sum(after[b])/len(after[b]), sum(allafter[b])/len(allafter[b])
                dd = [x - y for x, y in zip(allafter[b], allbase)]
                up = sum(1 for x in dd if x > 1e-9); dn = sum(1 for x in dd if x < -1e-9)
                pv = exact_p(dd)
                print(f"   {('ดัน ' + str(b)):<16}{m:>16.4f}{ma:>14.4f}"
                      f"   ดีขึ้น {up:2d} · แย่ลง {dn:2d} · p = {pv:.4f}"
                      + ("  ← มีนัยสำคัญ" if pv < 0.05 else ""))


if __name__ == "__main__":
    main()
