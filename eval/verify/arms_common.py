"""เทียบ 3 แขนบน **ชุดคำค้นร่วม** — คำค้นที่ทั้งสามแขนมีป้ายครบ

**ทำไมต้องมีไฟล์นี้** `eval/metrics_labelled.py` **ตัดคำค้นที่หาป้ายไม่ครบทิ้ง**
(ไม่ได้นับเป็น 0) แต่ละแขนจึงถูกตัดคนละข้อ → **ตัวเลขของแต่ละแขนมาจาก
ชุดคำค้นคนละชุด เทียบกันตรง ๆ ไม่ได้**

ไฟล์นี้หา**ส่วนร่วม**ก่อน แล้วจึงเทียบ พร้อมทดสอบสลับเครื่องหมายแบบนับครบทุกกรณี

⚠ ชุดร่วมจะเอนไปทางคำค้นที่ตัวจัดอันดับหยิบของที่**เคยติดป้ายแล้ว** คือคำค้นที่
ระบบใหม่ทำตัวเหมือนระบบเก่า → **ลำเอียงไปทางที่ทำให้เห็นความต่างน้อยกว่าจริง**
ทางแก้เดียวคือติดป้ายของที่โผล่ใหม่

รัน:  python eval\\verify\\arms_common.py eval\\results\\collection_20261016_1816.json
"""
from __future__ import annotations

import io
import json
import sys
from collections import defaultdict
from math import log2
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval.metrics_labelled import load_labels                     # noqa: E402

K = 3
IDCG = sum(3 / log2(i + 1) for i in range(1, K + 1))


def exact_p(diffs: list[float]) -> float:
    """ทดสอบสลับเครื่องหมายแบบนับครบทุกกรณี — รวมการแจกแจงด้วย DP
    (2^k ตรง ๆ ไม่ไหวที่ k หลายสิบ)

    ⚠ **ปัดค่าต่างเป็นจำนวนเต็มก่อน แล้วค่อยบวก** ห้ามปัดผลรวม —
    เคยเขียนเป็น `round(sum(...))` แล้วค่าที่สังเกตได้เกินค่าสูงสุดที่การแจกแจง
    ทำได้ 1 หน่วย ตัวเศษจึงเป็น 0 และคืน p = 0.0 ทั้งที่ค่าต่ำสุดที่เป็นไปได้
    คือ 2 / 2^k (เจอ 16 ต.ค. 2026 ตอนผลไทยให้ p = 0.0000 ที่ k = 3)
    """
    vals = [round(d * 1e6) for d in diffs if abs(d) > 1e-9]
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


def scores(rec: dict, qid: str, lab: dict) -> float | None:
    """nDCG@3 ของคำค้นเดียว · None = หยิบของที่ยังไม่มีป้าย"""
    gains = []
    for p in rec["picked"][:K]:
        g = lab.get((qid, p["title"]))
        if g is None:
            return None
        gains.append(g)
    gains += [0] * (K - len(gains))
    return sum(g / log2(i + 1) for i, g in enumerate(gains, 1)) / IDCG


def main(path: str) -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    lab = load_labels()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))["raw"]
    arms = [a for a in ("A1_r1", "A3C_r1", "A3_r1") if a in raw]

    # ---- ภาพรวมทุกกลุ่มรวมกัน ----
    # 🔑 ต้องมีด้วย เพราะคำถาม "agentic ดีกว่า rag ไหม" ตอบด้วยภาพรวม ไม่ใช่รายกลุ่ม
    # แยกรายกลุ่มแล้วจำนวนข้อที่ต่างกันเหลือน้อยจนไม่มีทางถึงนัยสำคัญ
    # (ชนะ 4 แพ้ 0 ให้ p ต่ำสุดได้แค่ 0.125 = ถึงเพดานแล้ว)
    allper: dict[str, dict[tuple[str, str], float]] = {a: {} for a in arms}
    for a in arms:
        for group in ("g1", "g4", "g3"):
            for qid, rec in raw[a].get(group, {}).items():
                v = scores(rec, qid, lab)
                if v is not None:
                    allper[a][(group, qid)] = v
    shared = sorted(set.intersection(*(set(allper[a]) for a in arms))) if arms else []
    total_all = sum(len(raw[arms[0]].get(g, {})) for g in ("g1", "g4", "g3")) if arms else 0
    print(f"\n===== ภาพรวมทุกกลุ่ม · ชุดร่วม {len(shared)} จาก {total_all} คำค้น")
    if shared:
        for a in arms:
            print(f"   {a:<8} nDCG@3 = {mean(allper[a][k] for k in shared):.4f}")
        base = arms[0]
        for a in arms[1:]:
            dd = [allper[a][k] - allper[base][k] for k in shared]
            up = sum(1 for x in dd if x > 1e-9)
            dn = sum(1 for x in dd if x < -1e-9)
            pv = exact_p(dd)
            print(f"   {base} ↔ {a:<6} {a} ดีขึ้น {up:2d} · แย่ลง {dn:2d} "
                  f"· เท่าเดิม {len(shared)-up-dn:3d} · p = {pv:.4f}"
                  + ("  ← มีนัยสำคัญ" if pv < 0.05 else ""))

    # ---- ความกล้าปฏิเสธเมื่อคลังไม่มีของ — ตัวชี้วัดที่ลูปแลกไป ----
    print("\n===== ปฏิเสธถูกเมื่อคลังไม่มีของ (ตัวชี้วัดที่ A1 มักชนะ)")
    for a in arms:
        n_ref = sum(1 for rec in raw[a].get("g3", {}).values() if not rec["picked"])
        print(f"   {a:<8} ปฏิเสธ {n_ref}/{len(raw[a].get('g3', {}))}")

    for group, gname in (("g1", "กลุ่ม 1 คลังมีของ"),
                         ("g4", "กลุ่ม 4 มีงบจำกัด"),
                         ("g3", "กลุ่ม 3 คลังไม่มีของ")):
        per: dict[str, dict[str, float]] = {}
        for a in arms:
            per[a] = {}
            for qid, rec in raw[a].get(group, {}).items():
                v = scores(rec, qid, lab)
                if v is not None:
                    per[a][qid] = v
        common = sorted(set.intersection(*(set(per[a]) for a in arms))) if arms else []
        total = len(raw[arms[0]].get(group, {})) if arms else 0
        print(f"\n===== {gname} · ชุดร่วม {len(common)} จาก {total} คำค้น")
        if not common:
            print("   ไม่มีคำค้นที่ทุกแขนมีป้ายครบ")
            continue
        for a in arms:
            print(f"   {a:<8} nDCG@3 = {mean(per[a][q] for q in common):.4f}")
        base = arms[0]
        for a in arms[1:]:
            dd = [per[a][q] - per[base][q] for q in common]
            up = sum(1 for x in dd if x > 1e-9)
            dn = sum(1 for x in dd if x < -1e-9)
            pv = exact_p(dd)
            print(f"   {base} ↔ {a:<6} {a} ดีขึ้น {up:2d} · แย่ลง {dn:2d} "
                  f"· เท่าเดิม {len(common)-up-dn:2d} · p = {pv:.4f}"
                  + ("  ← มีนัยสำคัญ" if pv < 0.05 else ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else "eval/results/collection_20261016_1816.json")
