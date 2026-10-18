r"""ช่วงคะแนนของ bge-m3 แคบแค่ไหน และการขยายช่องว่างช่วยหรือไม่

ตอบ 3 คำถาม
  1. ช่วงคะแนนที่ใช้งานจริงกว้างเท่าไร (ไม่ใช่ 0-1 อย่างที่สัญชาตญาณบอก)
  2. แคบเพราะอะไร — เหตุของโมเดล หรือเหตุของคลังเรา
  3. **ถ้าขยายช่องว่างออก คะแนน nDCG จะดีขึ้นไหม**

ข้อ 3 คือข้อค้นพบ · คำตอบคือ **ไม่** เพราะ nDCG สนใจแค่ลำดับ ไม่สนระยะห่าง
การแปลงเวกเตอร์เดิมไม่ได้เพิ่มข้อมูล ต้องใช้สัญญาณที่มาจากแหล่งอื่นเท่านั้น

⚠ ข้อ 3 จำกัดผู้เข้าชิงเฉพาะของมีป้าย เหมือน `rank_signals.py` (กัน pooling bias)

รัน:  python eval\verify\embed_space.py
"""
from __future__ import annotations

import io
import itertools
import json
import random
import sys
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from eval.collection import GROUP1_IN_DOMAIN, GROUP4_BUDGET        # noqa: E402
from eval.collection_th import GROUP1_TH, GROUP4_TH                # noqa: E402
from eval.verify.rank_signals import K, TH_LOG, load_labels, ndcg  # noqa: E402
from src.rerank import apply_gate, order_by_votes                  # noqa: E402
from retrieval import Retriever                                    # noqa: E402

PROBES = [("ตรงมาก", "wireless bluetooth earbuds"),
          ("ตรงมาก", "claw hammer"),
          ("ไม่เกี่ยวกับสินค้าเลย", "how do I file my taxes in Thailand"),
          ("ข้อความสุ่มไม่มีความหมาย", "qwzx plorbit fnarg"),
          ("ภาษาอื่นที่คลังไม่มี", "สวัสดีครับวันนี้อากาศดีมาก")]


def pick3(hits, text):
    """ชั้น 4 ย่อ — หยิบ K ชิ้น ห้ามร้านซ้ำ"""
    out, seen, skipped = [], set(), []
    for r in order_by_votes(hits, search_text=text):
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
    random.seed(0)
    lab = load_labels()

    with Retriever() as r:
        # ---- 1. ช่วงคะแนนที่ใช้งานจริง ----
        print("1) ช่วงคะแนนจริงของคำค้นห้าแบบ")
        print(f"   {'คำค้น':<36}{'อันดับ 1':>9}{'อันดับ 100':>12}")
        for tag, q in PROBES:
            h = r.search(q, k=100)
            print(f"   {q[:34]:<36}{h[0].score:>9.3f}{h[99].score:>12.3f}   {tag}")

        got = r.collection.get(limit=3000, include=["embeddings"])
        M = np.asarray(got["embeddings"], dtype=np.float32)
        M /= np.linalg.norm(M, axis=1, keepdims=True)
        mu = M.mean(axis=0)
        mu /= np.linalg.norm(mu)
        Vt = np.linalg.svd(M - M.mean(axis=0), full_matrices=False)[2]
        PCs = Vt[:3]

        # ---- 2. แคบเพราะอะไร ----
        idx = random.sample(range(len(M)), 120)
        sims = np.array([float(M[i] @ M[j]) for i, j in itertools.combinations(idx, 2)])
        print(f"\n2) ความคล้ายระหว่างสินค้าสองชิ้นที่สุ่มมา ({len(sims):,} คู่)")
        print(f"   ต่ำสุด {sims.min():.3f} · เฉลี่ย {sims.mean():.3f} · สูงสุด {sims.max():.3f}")
        print("   ถ้ากระจายทั่วทรงกลม 1024 มิติ ค่าเฉลี่ยควรเป็น ~0.000")
        proj = M @ mu
        print(f"   โปรเจกต์ลงทิศเฉลี่ยของคลัง · เฉลี่ย {proj.mean():.3f}"
              f" (ใกล้ 1 = อัดกันในกรวยแคบ)")

        # ---- 3. ขยายช่องว่างแล้วคะแนนขึ้นไหม ----
        print("\n3) 🔑 ขยายช่องว่างแล้ว nDCG@3 ดีขึ้นไหม")
        for langname, pairs in queries():
            base, cen, pca = [], [], []
            for qid, text in pairs:
                hits = [h for h in apply_gate(r.search(text, k=100), 0.55)
                        if (qid, h.title[:40]) in lab]
                if len(hits) < K:
                    continue
                emb = r.collection.get(ids=[h.id for h in hits], include=["embeddings"])
                E = {i: np.asarray(v, dtype=np.float32)
                     for i, v in zip(emb["ids"], emb["embeddings"])}
                qv = np.asarray(r.embed_query(text), dtype=np.float32)
                qv /= np.linalg.norm(qv)
                base.append(ndcg(pick3(hits, text), qid, lab))
                for mode, box in (("cen", cen), ("pca", pca)):
                    def fix(v, mode=mode):
                        v = v / np.linalg.norm(v)
                        v = (v - (v @ mu) * mu if mode == "cen"
                             else v - sum((v @ p) * p for p in PCs))
                        return v / np.linalg.norm(v)
                    q2 = fix(qv)
                    for h in hits:
                        h.score = float(q2 @ fix(E[h.id]))
                    box.append(ndcg(pick3(hits, text), qid, lab))
            b = mean(base)
            print(f"\n   ===== {langname} · {len(base)} คำค้น")
            print(f"      คะแนนเดิม                    nDCG@3 = {b:.4f}")
            print(f"      ลบทิศเฉลี่ยออก               nDCG@3 = {mean(cen):.4f}"
                  f"  ({(mean(cen)-b)*100:+.1f} จุด)")
            print(f"      ลบองค์ประกอบหลัก 3 ตัวแรก    nDCG@3 = {mean(pca):.4f}"
                  f"  ({(mean(pca)-b)*100:+.1f} จุด)")


if __name__ == "__main__":
    main()
