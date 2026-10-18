"""ขั้นที่ 2 — วัดสัญญาณที่ 6 "ข้อกำหนดที่ขาดไม่ได้"

ตอบ 3 คำถาม
  1. ให้โค้ดหาคำที่ขาดเองล้วน ๆ ช่วยไหม
  2. ให้ LLM เลือกจากรายการที่โค้ดหามา **เพิ่มอะไรขึ้นมาไหม**
  3. น้ำหนักเท่าไรดี

⚠ จำกัดผู้เข้าชิงเฉพาะของมีป้าย เหมือน `rank_signals.py` (กัน pooling bias)
⚠ ค่าที่ได้ไม่ใช่ค่าปลายทางจริง ใช้เทียบวิธีต่อวิธีเท่านั้น

รัน:  python eval\\verify\\must_terms.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from statistics import mean

# ⚠ ตั้ง wrapper ใน main() ไม่ใช่ตอน import — ไม่งั้น rank_signals.py ตั้งซ้ำ
# แล้วตัวแรกถูกเก็บขยะ ทำให้ buffer ปิดไปด้วย
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval.collection import GROUP1_IN_DOMAIN, GROUP4_BUDGET       # noqa: E402
from eval.collection_th import GROUP1_TH, GROUP4_TH               # noqa: E402
from eval.verify.rank_signals import (K, TH_LOG, exact_p,         # noqa: E402
                                      load_labels, ndcg)
from src.critique import _candidate_terms, missing_terms          # noqa: E402
from src.rerank import apply_gate, order_by_votes                 # noqa: E402
from src.retrieval import Retriever                               # noqa: E402

WEIGHTS = [6, 12, 24]


def pick(hits, search_text, must=None, w_must=12):
    ranked = order_by_votes(hits, search_text=search_text,
                            must_terms=must, w_must=w_must)
    out, seen, skipped = [], set(), []
    for r in ranked:
        st = r.hit.store
        if st is not None and st in seen:
            skipped.append(r.hit)
            continue
        out.append(r.hit)
        if st is not None:
            seen.add(st)
        if len(out) == K:
            return out
    return (out + skipped)[:K]


def queries():
    th_log = json.loads(TH_LOG.read_text(encoding="utf-8"))["raw"]["A3C_r1"]
    en = ([(x["id"], x["q"]) for x in GROUP1_IN_DOMAIN]
          + [(x["id"], x["q"]) for x in GROUP4_BUDGET])
    th = []
    for grp, table in (("g1", GROUP1_TH), ("g4", GROUP4_TH)):
        for qid in table:
            st = (th_log.get(grp, {}).get(qid, {}).get("search_texts") or [None])[0]
            if st:
                th.append((qid, st))
    return (("ไทย", th), ("อังกฤษ", en))


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    lab = load_labels()
    with Retriever() as r:
        for langname, pairs in queries():
            cols: dict[str, list[float]] = {"base": []}
            for w in WEIGHTS:
                cols[f"code{w}"] = []
                cols[f"llm{w}"] = []
            n_code = n_llm = n_drop = 0
            for qid, text in pairs:
                hits = [h for h in apply_gate(r.search(text, k=100), 0.55)
                        if (qid, h.title[:40]) in lab]
                if len(hits) < K:
                    continue
                top0 = pick(hits, text)
                base = ndcg(top0, qid, lab)
                cols["base"].append(base)

                titles = [h.title for h in top0]
                code = _candidate_terms(text, titles)
                llm = missing_terms(text, titles) if code else []
                n_code += bool(code)
                n_llm += bool(llm)
                n_drop += bool(code) and not llm
                for w in WEIGHTS:
                    cols[f"code{w}"].append(
                        ndcg(pick(hits, text, code, w), qid, lab) if code else base)
                    cols[f"llm{w}"].append(
                        ndcg(pick(hits, text, llm, w), qid, lab) if llm else base)

            n = len(cols["base"])
            b = cols["base"]
            print(f"\n===== {langname} · {n} คำค้น")
            print(f"   โค้ดหาคำที่ขาดได้ {n_code} ข้อ ({n_code/max(1,n):.0%}) · "
                  f"LLM เก็บไว้ {n_llm} ข้อ · LLM ทิ้งทั้งหมด {n_drop} ข้อ")
            print(f"   {'วิธี':<26}{'nDCG@3':>9}{'ต่าง':>8}   รายละเอียด")
            print(f"   {'ไม่มีสัญญาณที่ 6':<26}{mean(b):>9.4f}")
            for tag, label in (("code", "โค้ดล้วน"), ("llm", "โค้ด + LLM เลือก")):
                for w in WEIGHTS:
                    col = cols[f"{tag}{w}"]
                    dd = [x - y for x, y in zip(col, b)]
                    up = sum(1 for x in dd if x > 1e-9)
                    dn = sum(1 for x in dd if x < -1e-9)
                    pv = exact_p(dd)
                    print(f"   {f'{label} น้ำหนัก {w}':<26}{mean(col):>9.4f}"
                          f"{(mean(col)-mean(b))*100:>+8.1f}   "
                          f"ดีขึ้น {up:2d} · แย่ลง {dn:2d} · p = {pv:.4f}"
                          + ("  ← มีนัยสำคัญ" if pv < 0.05 else ""))


if __name__ == "__main__":
    main()
