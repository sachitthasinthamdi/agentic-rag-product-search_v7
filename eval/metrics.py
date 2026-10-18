"""คิดตัวชี้วัดจากผลดิบของ `eval/run_collection.py`

**ไฟล์นี้คิดเฉพาะตัวชี้วัดที่ไม่ต้องใช้ป้ายจากคน** (ช่อง ❌ ในตาราง `docs/eval_plan.md`)
ส่วนที่ต้องใช้ป้าย (nDCG@3 · P@3 · Recall@100 · ความซื่อตรง) อยู่ใน `eval/metrics_labelled.py`
ซึ่งเขียนหลังติดป้ายเสร็จ — แยกไฟล์เพราะคิดได้คนละเวลากัน

ตัวชี้วัดในไฟล์นี้
  ส่วน ก  อัตราละเมิดงบ · ความแม่นของการตัดสินใจแนะนำ/ปฏิเสธ · ความหลากหลายของร้าน · ต้นทุน
  ส่วน ข  ความครบถ้วน · ภาษาตรงกับผู้ใช้ · ไม่แต่งตัวเลข
  ความเสถียร  ความคงเส้นคงวาข้ามรอบ (ต้องมี >= 2 รอบ)

รัน:  python eval\\metrics.py eval\\results\\collection_20261003_1957.json
      python eval\\metrics.py <ไฟล์> --json       (ให้เครื่องอ่านต่อ)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from generate import verify_reply                                # noqa: E402
from translate import thai_ratio                                 # noqa: E402

# ---------------------------------------------------------------------------
# งบประมาณ
#
# ⚠ **อ่านงบจากข้อความคำค้น ไม่ใช่จากฟิลด์ `budget` ในชุดทดสอบ**
# เพราะชุดทดสอบไม่ตรงกันเอง 1 ข้อ: "baby proofing cabinet lock bows under $6"
# ข้อความบอก $6 แต่ฟิลด์เก็บไว้ 5.5 (ตอนสร้างปัดเลขในข้อความแต่ไม่ปัดในฟิลด์)
# **สิ่งที่ผู้ใช้ขอคือสิ่งที่เขาพิมพ์** จึงยึดข้อความ และไม่แก้ไฟล์ที่ล็อกแล้ว
#
# ⚠ "under $11" แปลว่า "ต่ำกว่า" หรือ "ไม่เกิน" — ภาษาอังกฤษแปลว่าต่ำกว่า
# แต่ Reranker ใช้เกณฑ์ `ราคา <= งบ` **รายงานทั้งสองแบบ** ให้ผู้อ่านตัดสินเอง
# ตัวหลักคือแบบไม่เกิน (<=) เพราะตรงกับเกณฑ์ที่ระบบใช้จริง
# ---------------------------------------------------------------------------

# ⚠ ต้องอ่านได้ทั้ง 2 ภาษา — รอบไทยเขียนงบว่า "ไม่เกิน 11 ดอลลาร์" ไม่มีสัญลักษณ์ $
# ถ้าอ่านเฉพาะ $ รอบไทยจะรายงานว่า "ไม่มีคำค้นที่มีงบ" ทั้งที่มี 30 คำ
_BUDGET = re.compile(r"\$\s*([0-9]+(?:\.[0-9]+)?)"
                     r"|([0-9]+(?:\.[0-9]+)?)\s*ดอลลาร์")


def budget_in_query(q: str) -> float | None:
    m = _BUDGET.search(q)
    return float(m.group(1) or m.group(2)) if m else None


# ---------------------------------------------------------------------------
# เครื่องมือเล็ก ๆ
# ---------------------------------------------------------------------------

def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d * 100:4.1f}%)" if d else f"0/0 ( — )"


def recommended(rec: dict) -> bool:
    """ระบบแนะนำสินค้าไหม (ตรงข้ามกับงดตอบ)"""
    return bool(rec["picked"])


def mentions(rec: dict, p: dict) -> bool:
    """คำตอบพูดถึงสินค้าชิ้นนี้ไหม — จับจาก 4 คำแรกของชื่อ

    ไม่ใช่การจับที่สมบูรณ์ (ถ้าโมเดลถอดความชื่อใหม่จะจับไม่ได้) แต่หลังแก้บั๊ก
    ชั้นเขียนคำตอบแล้ว **โค้ดเป็นคนใส่ชื่อเอง** การจับจึงแม่นโดยโครงสร้าง
    """
    key = " ".join(p["title"].lower().split()[:4])
    return bool(key) and key in rec["reply"].lower()


# ---------------------------------------------------------------------------
# ส่วน ก — การดึงข้อมูล
# ---------------------------------------------------------------------------

def budget_violation(g4: dict) -> dict:
    """อัตราละเมิดงบ — นับทั้งรายชิ้นและรายคำถาม

    รายคำถามสำคัญกว่า: ผู้ใช้เห็นคำตอบทั้งก้อน ถ้ามีของเกินงบปนมา 1 ชิ้น
    ก็ถือว่าคำตอบนั้นผิดสัญญาแล้ว
    """
    out = {"n_queries": 0, "n_items": 0, "no_budget_read": 0,
           "over_le": 0, "over_lt": 0, "q_over_le": 0, "q_over_lt": 0,
           "no_price": 0, "examples": []}
    for rec in g4.values():
        b = budget_in_query(rec["q"])
        if b is None:
            out["no_budget_read"] += 1
            continue
        out["n_queries"] += 1
        bad_le = bad_lt = 0
        for p in rec["picked"]:
            out["n_items"] += 1
            if p["price"] is None:
                out["no_price"] += 1
                continue
            if p["price"] > b:
                bad_le += 1
            if p["price"] >= b:
                bad_lt += 1
        out["over_le"] += bad_le
        out["over_lt"] += bad_lt
        out["q_over_le"] += int(bad_le > 0)
        out["q_over_lt"] += int(bad_lt > 0)
        if bad_le and len(out["examples"]) < 5:
            worst = max((p for p in rec["picked"] if p["price"] is not None),
                        key=lambda p: p["price"])
            out["examples"].append((rec["q"], b, worst["price"], worst["title"][:50]))
    return out


def abstention(g1: dict, g3: dict) -> dict:
    """ความแม่นของการ**ตัดสินใจว่าจะแนะนำหรือปฏิเสธ** — วัดสองด้าน

    วัดทางเดียวไม่ได้ — ระบบที่ตอบ "ไม่พบ" ทุกคำถามจะได้คะแนนเต็มในกลุ่ม 3
    จึงต้องดูคู่กับกลุ่ม 1 ว่ามันยังแนะนำของตอนที่คลังมีของอยู่ไหม
    """
    tp = sum(1 for r in g3.values() if not recommended(r))   # ไม่มีของ -> ปฏิเสธ ✅
    fn = len(g3) - tp                                        # ไม่มีของ -> ยัดของมา ❌
    ok = sum(1 for r in g1.values() if recommended(r))       # มีของ -> แนะนำ ✅
    over = len(g1) - ok                                      # มีของ -> ปฏิเสธ ❌ งดตอบเกินเหตุ
    bal = (tp / len(g3) + ok / len(g1)) / 2 if g1 and g3 else 0.0
    return {"g3_refused_ok": tp, "g3_total": len(g3), "g3_leaked": fn,
            "g1_served_ok": ok, "g1_total": len(g1), "g1_over_abstain": over,
            "balanced": bal}


def store_diversity(groups: dict) -> dict:
    """ความหลากหลายของร้าน (Ziegler et al. 2005)

    Reranker ชั้นที่ 4 กันร้านซ้ำอยู่แล้ว ตัวเลขนี้จึงเป็น**การตรวจว่าชั้นนั้นทำงาน**
    มากกว่าจะเป็นตัวชี้วัดคุณภาพ
    """
    rates, dup = [], 0
    for items in groups.values():
        for rec in items.values():
            picks = rec["picked"]
            if not picks:
                continue
            stores = {(p["store"] or "").strip().lower() for p in picks}
            rates.append(len(stores) / len(picks))
            dup += int(len(stores) < len(picks))
    return {"mean_ratio": mean(rates) if rates else 0.0,
            "n_with_duplicate_store": dup, "n_answered": len(rates)}


def cost(groups: dict) -> dict:
    v = [r for items in groups.values() for r in items.values()]
    def stat(f):
        xs = [r[f] for r in v]
        return {"mean": mean(xs), "median": median(xs), "max": max(xs)}
    return {"n": len(v), "llm_calls": stat("llm_calls"),
            "n_searches": stat("n_searches"), "seconds": stat("seconds")}


# ---------------------------------------------------------------------------
# ส่วน ข — คำตอบ
#
# ⚠ **กรองคำตอบที่โค้ดเขียนเองออกก่อนวัด** (โหมดอ่อน) — มันซื่อตรง 100%
# โดยโครงสร้าง ถ้านับรวมจะเป็นการให้คะแนนฟรี · ต้องรายงานสัดส่วนที่กรองออกด้วย
# ---------------------------------------------------------------------------

def answer_quality(groups: dict) -> dict:
    """⚠ **ภาษาที่ควรตอบดูจากคำค้นทีละข้อ ไม่ใช่ตั้งค่ารวมทั้งรอบ**

    รอบไทยมีคำค้นอังกฤษปนอยู่ 45 คำในกลุ่ม 3 (ชื่อคน ชื่อหนังสือ ที่แปลไม่ได้)
    ถ้าตั้งว่า "ทั้งรอบควรตอบไทย" คำพวกนั้นจะถูกนับว่าผิดทั้งที่ระบบทำถูก
    """
    graded, weak_n, empty_n = [], 0, 0
    for items in groups.values():
        for rec in items.values():
            if not rec["picked"]:
                empty_n += 1
            elif rec["weak"]:
                weak_n += 1
            else:
                graded.append(rec)

    complete = sum(1 for r in graded
                   if all(mentions(r, p) for p in r["picked"]))
    lang_ok = sum(1 for r in graded
                  if (thai_ratio(r["reply"]) > 0.15)
                  == (thai_ratio(r["q"]) > 0.15))
    # ⚠ **คิดใหม่ ไม่ใช้ค่าที่บันทึกไว้** — ผลรันก่อนหน้าเรียก `verify_reply()`
    # โดยไม่ส่งคำถามเข้าไป เลขที่ผู้ใช้พิมพ์เองจึงถูกตั้งธงผิด
    # คิดใหม่จาก reply + context + q ที่เก็บไว้ครบแล้ว -> ไม่ต้องรันระบบซ้ำ
    flagged = {id(r): verify_reply(r["reply"], r["context"], r["q"])
               for r in graded}
    clean = sum(1 for r in graded if not flagged[id(r)])
    ctx = sum(1 for r in graded if r["context"])
    bad = [(r["q"], flagged[id(r)]) for r in graded if flagged[id(r)]][:5]
    return {"n_graded": len(graded), "n_weak_filtered": weak_n,
            "n_empty": empty_n, "complete": complete, "lang_ok": lang_ok,
            "no_made_up_numbers": clean, "has_context": ctx,
            "examples_made_up": bad}


# ---------------------------------------------------------------------------
# ความเสถียรข้ามรอบ — ต้องรันอย่างน้อย 2 รอบ
# ---------------------------------------------------------------------------

def consistency(rounds: list[dict]) -> dict | None:
    """ตอบเหมือนเดิมทุกรอบไหม — แนวคิด pass^k (Yao et al. 2024, tau-bench)

    วัด 2 ระดับ
      outcome  ตัดสินใจเหมือนเดิมไหม (แนะนำ / ปฏิเสธ)
      picks    เลือกสินค้าชุดเดียวกันเป๊ะไหม  <- เข้มกว่า
    """
    if len(rounds) < 2:
        return None
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in rounds:
        for items in r.values():
            for qid, rec in items.items():
                by_q[qid].append(rec)
    same_out = same_pick = 0
    full = [v for v in by_q.values() if len(v) == len(rounds)]
    for v in full:
        if len({recommended(x) for x in v}) == 1:
            same_out += 1
        if len({tuple(p["id"] for p in x["picked"]) for x in v}) == 1:
            same_pick += 1
    return {"k": len(rounds), "n": len(full),
            "same_outcome": same_out, "same_picks": same_pick}


# ---------------------------------------------------------------------------
# รายงาน
# ---------------------------------------------------------------------------

def compute(raw: dict, arm_round: str) -> dict:
    g = raw[arm_round]
    return {"arm_round": arm_round,
            "budget": budget_violation(g.get("g4", {})),
            "abstention": abstention(g.get("g1", {}), g.get("g3", {})),
            "diversity": store_diversity(g),
            "cost": cost(g),
            "answer": answer_quality(g)}


def report(m: dict) -> None:
    b, a, d, c, ans = (m["budget"], m["abstention"], m["diversity"],
                       m["cost"], m["answer"])
    print(f"\n{'=' * 74}\n  {m['arm_round']}  — ตัวชี้วัดที่ไม่ต้องใช้ป้าย\n{'=' * 74}")

    print("\n## ส่วน ก — การดึงข้อมูล\n")
    print("### การตัดสินใจว่าจะแนะนำหรือปฏิเสธ (วัดสองด้าน)")
    print(f"  คลังไม่มีของ -> ปฏิเสธถูก     {pct(a['g3_refused_ok'], a['g3_total'])}")
    print(f"  คลังมีของ   -> แนะนำได้       {pct(a['g1_served_ok'], a['g1_total'])}")
    print(f"  ** คะแนนตัดสินใจแนะนำ/ปฏิเสธ  {a['balanced'] * 100:4.1f}%")
    if a["g3_leaked"]:
        print(f"  ⚠ ยัดของมาทั้งที่คลังไม่มี    {a['g3_leaked']} คำ")
    if a["g1_over_abstain"]:
        print(f"  ⚠ ปฏิเสธทั้งที่คลังมีของ      {a['g1_over_abstain']} คำ")

    print("\n### การทำตามงบ")
    if not b["n_queries"]:
        print("  (ไม่มีคำค้นที่มีงบ)")
    else:
        print(f"  อ่านงบจากข้อความไม่ได้        {b['no_budget_read']} คำ")
        print(f"  เกินงบ รายชิ้น  (ราคา > งบ)   {pct(b['over_le'], b['n_items'])}")
        print(f"  เกินงบ รายคำถาม (ราคา > งบ)   {pct(b['q_over_le'], b['n_queries'])}  <- ตัวหลัก")
        print(f"  ถ้าตีความเข้ม  (ราคา >= งบ)   {pct(b['q_over_lt'], b['n_queries'])}")
        if b["no_price"]:
            print(f"  สินค้าไม่มีราคา (ข้ามไป)      {b['no_price']} ชิ้น")
        for q, bud, price, title in b["examples"]:
            print(f"     ⚠ \"{q[:40]}\"  งบ ${bud} แต่ได้ ${price} — {title}")

    print("\n### ความหลากหลายของร้าน")
    print(f"  ร้านไม่ซ้ำเฉลี่ย              {d['mean_ratio'] * 100:4.1f}% ของชิ้นที่แนะนำ")
    print(f"  คำตอบที่มีร้านซ้ำ             {pct(d['n_with_duplicate_store'], d['n_answered'])}")

    print("\n### ต้นทุน")
    print(f"  {'':<22}{'เฉลี่ย':>9}{'กลาง':>9}{'สูงสุด':>9}")
    for label, key in (("เรียก LLM (ครั้ง)", "llm_calls"),
                       ("ค้นในคลัง (รอบ)", "n_searches"),
                       ("เวลา (วินาที)", "seconds")):
        s = c[key]
        print(f"  {label:<22}{s['mean']:>9.2f}{s['median']:>9.2f}{s['max']:>9.2f}")

    print("\n## ส่วน ข — คำตอบ\n")
    n = ans["n_graded"]
    print(f"  วัดจาก {n} คำตอบ  (กรองโหมดอ่อน {ans['n_weak_filtered']} · "
          f"ไม่มีสินค้า {ans['n_empty']})")
    print(f"  เขียนสินค้าครบทุกชิ้น         {pct(ans['complete'], n)}")
    print(f"  ภาษาตรงกับที่ผู้ใช้ใช้        {pct(ans['lang_ok'], n)}")
    print(f"  ไม่มีตัวเลขที่แต่งขึ้น        {pct(ans['no_made_up_numbers'], n)}")
    print(f"  เก็บข้อเท็จจริงไว้ติดป้ายได้  {pct(ans['has_context'], n)}")
    for q, nums in ans["examples_made_up"]:
        print(f"     ⚠ \"{q[:44]}\"  ตัวเลขไม่มีหลักฐาน {nums}")

    print(f"\n{'-' * 74}")
    print("⚠ ยังขาดตัวหลัก — nDCG@3 · P@3 · Recall@100 · ความซื่อตรงของคำตอบ")
    print("  ทั้งหมดต้องรอป้ายจากคน · ดู docs/eval_plan.md หัวข้อ 5")


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="คิดตัวชี้วัดที่ไม่ต้องใช้ป้าย")
    ap.add_argument("results", type=Path)
    ap.add_argument("--json", action="store_true", help="พิมพ์เป็น JSON")
    args = ap.parse_args()

    data = json.loads(args.results.read_text(encoding="utf-8"))
    raw = data["raw"]
    out = {k: compute(raw, k) for k in sorted(raw)}

    stab = consistency([raw[k] for k in sorted(raw)])
    if args.json:
        print(json.dumps({"metrics": out, "consistency": stab},
                         ensure_ascii=False, indent=1))
        return
    for m in out.values():
        report(m)
    print(f"\n{'=' * 74}\n  ความเสถียรข้ามรอบ\n{'=' * 74}")
    if stab is None:
        print("  รันรอบเดียว — วัดความเสถียรไม่ได้ ต้องรันอย่างน้อย 2 รอบ")
    else:
        print(f"  เทียบ {stab['k']} รอบ · {stab['n']} คำค้น")
        print(f"  ตัดสินใจเหมือนเดิมทุกรอบ      {pct(stab['same_outcome'], stab['n'])}")
        print(f"  เลือกสินค้าชุดเดิมเป๊ะทุกรอบ  {pct(stab['same_picks'], stab['n'])}")


if __name__ == "__main__":
    main()
