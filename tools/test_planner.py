"""ทดสอบว่า Typhoon2-8B ตัดสินใจเป็น Planner ได้แม่นพอไหม

**ตอบ 3 คำถาม**

  1. **แม่นไหม**      — เทียบกับคำตอบที่คนติดป้ายไว้
  2. **นิ่งไหม**       — ถามซ้ำ 3 รอบ ได้คำตอบเดิมทุกรอบหรือเปล่า
  3. **ดีกว่ากฎไหม**  — เทียบกับโค้ดที่ตัดสินด้วยกฎล้วน ๆ

**ข้อ 3 สำคัญที่สุด** เพราะถ้า LLM ไม่ดีกว่ากฎ ก็ทำนายได้เลยว่า **A4 จะไม่ดีกว่า A3**
→ รู้ตอนนี้ยังเปลี่ยนโมเดลหรือลดขอบเขตทัน ก่อนลงแรงสร้าง A4

วัด **ความแม่น** และ **Cohen's κ** (κ แก้ผลของการเดาถูกโดยบังเอิญ ซึ่งสำคัญเพราะ
คำตอบกระจายไม่เท่ากัน — ถ้าตอบ `recommend` รัว ๆ ก็ได้ความแม่น 59% ฟรี ๆ)

เกณฑ์ของ Landis & Koch (1977): <0.20 แทบไม่สอดคล้อง · 0.21-0.40 เล็กน้อย ·
0.41-0.60 พอใช้ · 0.61-0.80 ดี · >0.80 ดีมาก

รัน:  python tools\\test_planner.py [--rounds 3]
⚠ ต้องสตาร์ต Ollama ก่อน · ใช้เวลาราว 5-8 นาที
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import planner                                                   # noqa: E402
from eval.planner_cases import A2_CASES, LOOP_CASES              # noqa: E402
from memory import Profile, _chat_json                           # noqa: E402

# ---------------------------------------------------------------------------
# พรอมต์ของการตัดสินใจวนลูป (A4) — ยังไม่มีในโค้ดจริง สร้างที่นี่เพื่อทดสอบก่อนสร้าง A4
#
# ⚠ **จงใจไม่บอกเกณฑ์ตัวเลข** เพราะถ้าบอก "ต่ำกว่า 3 ชิ้นให้ค้นใหม่" ก็เท่ากับ
# เอากฎของ A3 ไปให้ LLM อ่าน → ไม่ได้วัดการตัดสินใจของ LLM เอง และ A4 จะกลายเป็น A3
# ---------------------------------------------------------------------------
LOOP_SYSTEM = """คุณคือ Planner ของระบบแนะนำสินค้า ระบบค้นของมาแล้วรอบหนึ่ง
ตัดสินว่าควรทำอะไรต่อ

- "search": ของที่ได้ยังไม่ดีพอ และยังมีโอกาสที่การค้นด้วยคำอื่นจะได้ผลดีขึ้น
- "answer": ของที่ได้ดีพอจะตอบผู้ใช้แล้ว หรือค้นต่อก็ไม่น่าจะดีขึ้น

ระบบต้องแนะนำสินค้าให้ผู้ใช้ 3 ชิ้น

ตอบ JSON: {"action": "...", "reason": "เหตุผลสั้น ๆ"}"""

LOOP_ACTIONS = ("search", "answer")


def kappa(a: list[str], b: list[str]) -> float:
    """Cohen's κ — เขียนเอง เพราะ sklearn ใช้บนเครื่องนี้ไม่ได้"""
    n = len(a)
    if n == 0:
        return 0.0
    labels = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def band(k: float) -> str:
    for edge, name in ((0.20, "แทบไม่สอดคล้อง"), (0.40, "สอดคล้องเล็กน้อย"),
                       (0.60, "พอใช้"), (0.80, "ดี")):
        if k <= edge:
            return name
    return "ดีมาก"


# ---------------------------------------------------------------------------
def ask_loop(case: dict) -> str:
    """ถาม LLM ว่าควรค้นใหม่หรือตอบ"""
    user = (f"จำนวนสินค้าที่ผ่านเกณฑ์ความตรง: {case['passed']} ชิ้น\n"
            f"ค้นมาแล้ว: {case['rounds']} ครั้ง\n"
            f"คำค้นที่ลองไปแล้ว: {', '.join(case['tried'])}\n"
            f"เลือก action")
    result = _chat_json(LOOP_SYSTEM, user)
    return str(result.get("action", "")).strip().lower()


def rule_loop(case: dict) -> str:
    """กฎของ A3 — โค้ดล้วน ทำซ้ำได้ 100%"""
    return "search" if case["passed"] < 3 and case["rounds"] < 2 else "answer"


def rule_a2(case: dict) -> str:
    """กฎล้วนสำหรับ A2 — ใช้ `planner.fallback()` ตัวจริง"""
    return planner.fallback(Profile(**case["profile"]), case["asks"]).action


# ---------------------------------------------------------------------------
def run(name: str, cases: list[dict], rounds: int,
        llm_fn, rule_fn, final_fn=None) -> dict:
    print(f"\n{'=' * 78}\n{name}\n{'=' * 78}")
    gold = [c["expect"] for c in cases]
    rule = [rule_fn(c) for c in cases]

    raw_rounds: list[list[str]] = []
    final_rounds: list[list[str]] = []
    for _ in range(rounds):
        raw_rounds.append([llm_fn(c) for c in cases])
        if final_fn:
            final_rounds.append([final_fn(c) for c in cases])

    hdr = f"{'id':<5}{'ที่ถูก':<12}{'กฎล้วน':<12}" + "".join(
        f"{'LLM ร' + str(i + 1):<12}" for i in range(rounds)) + "นิ่ง"
    print(hdr)
    print("-" * len(hdr))
    stable = 0
    for i, c in enumerate(cases):
        outs = [r[i] for r in raw_rounds]
        same = len(set(outs)) == 1
        stable += same
        cells = "".join(f"{(o or 'ว่าง'):<12}" for o in outs)
        print(f"{c['id']:<5}{gold[i]:<12}{rule[i]:<12}{cells}"
              f"{'ใช่' if same else '**ไม่**'}")

    # ใช้รอบแรกเป็นตัวแทนในการวัดความแม่น
    raw = raw_rounds[0]
    acc_raw = sum(1 for x, y in zip(raw, gold) if x == y) / len(gold)
    acc_rule = sum(1 for x, y in zip(rule, gold) if x == y) / len(gold)
    out = {"name": name, "n": len(cases), "stable": stable / len(cases),
           "acc_raw": acc_raw, "k_raw": kappa(raw, gold),
           "acc_rule": acc_rule, "k_rule": kappa(rule, gold)}

    print(f"\n{'':<26}{'ความแม่น':>10}{'Cohen κ':>12}  ระดับ")
    print(f"{'LLM ดิบ ๆ':<26}{acc_raw:>9.1%}{out['k_raw']:>12.3f}  {band(out['k_raw'])}")
    if final_fn:
        final = final_rounds[0]
        acc_f = sum(1 for x, y in zip(final, gold) if x == y) / len(gold)
        k_f = kappa(final, gold)
        out.update({"acc_final": acc_f, "k_final": k_f})
        print(f"{'LLM + โค้ดช่วย':<26}{acc_f:>9.1%}{k_f:>12.3f}  {band(k_f)}")
    print(f"{'กฎล้วน (ไม่ใช้ LLM)':<26}{acc_rule:>9.1%}"
          f"{out['k_rule']:>12.3f}  {band(out['k_rule'])}")
    print(f"\nตอบเหมือนกันทุกรอบ {stable}/{len(cases)} ข้อ "
          f"({stable / len(cases):.0%})")

    bad = [c["id"] for i, c in enumerate(cases) if raw[i] != gold[i]]
    if bad:
        print(f"ข้อที่ LLM ตอบผิด (รอบ 1): {', '.join(bad)}")
    return out


def final_a2(case: dict) -> str:
    """ผลสุดท้ายของ A2 หลังโค้ดกันการถามพร่ำเพรื่อแล้ว"""
    return planner.decide(Profile(**case["profile"]),
                          case["message"], case["asks"]).action


def llm_a2(case: dict) -> str:
    """ผลดิบจาก LLM ก่อนโค้ดเข้าไปแก้ — เรียกพรอมต์เดียวกับ planner.decide()"""
    user = (f"โปรไฟล์: {json.dumps(Profile(**case['profile']).to_dict(), ensure_ascii=False)}\n"
            f'ข้อความล่าสุด: "{case["message"]}"\n'
            f"ถามกลับไปแล้ว {case['asks']} ครั้ง\nเลือก action")
    result = _chat_json(planner.PLAN_SYSTEM, user)
    return str(result.get("action", "")).strip().lower()


def main() -> None:
    ap = argparse.ArgumentParser(description="ทดสอบความน่าเชื่อถือของ Planner")
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    r1 = run("ชุดที่ 1 — Planner ของ A2 (chat / ask / recommend)",
             A2_CASES, args.rounds, llm_a2, rule_a2, final_a2)
    r2 = run("ชุดที่ 2 — การตัดสินใจวนลูปของ A4 (search / answer)  ** สำคัญที่สุด **",
             LOOP_CASES, args.rounds, ask_loop, rule_loop)

    print(f"\n{'=' * 78}\nสรุป\n{'=' * 78}")
    print(f"{'ชุด':<42}{'LLM κ':>9}{'กฎล้วน κ':>11}{'นิ่ง':>8}")
    for r in (r1, r2):
        print(f"{r['name'][:40]:<42}{r['k_raw']:>9.3f}{r['k_rule']:>11.3f}"
              f"{r['stable']:>8.0%}")

    print("\nอ่านผล")
    print("  ถ้า LLM κ สูงกว่ากฎล้วนชัดเจน  -> A4 มีโอกาสดีกว่า A3 คุ้มที่จะสร้าง")
    print("  ถ้าใกล้กันหรือต่ำกว่า            -> A4 ไม่น่าจะดีกว่า A3 (เป็นข้อค้นพบที่ลงเล่มได้)")
    print("  ถ้า 'นิ่ง' ต่ำ                   -> A4 ทำซ้ำไม่ได้ กระทบความน่าเชื่อถือของผลวัด")


if __name__ == "__main__":
    main()
