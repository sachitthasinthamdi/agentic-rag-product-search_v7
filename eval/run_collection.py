"""รันแขนบนชุดทดสอบที่ล็อกไว้ (`eval/collection.py`) แล้วบันทึกผลดิบ

**ไฟล์นี้ไม่คิดตัวชี้วัด** — แค่รันและเก็บผล · การคิดตัวชี้วัดอยู่ที่ `eval/metrics.py`
เพราะ nDCG ต้องรอป้ายจากคน ซึ่งติดทีหลังจากผลที่ไฟล์นี้บันทึก

**บันทึกทีละข้อ** — รอบแรกที่รันเต็มถูกฆ่ากลางทางเพราะ Ollama ตาย งาน 10 นาทีหายหมด

รัน:  python eval\\run_collection.py --arms A3 --rounds 3
      python eval\\run_collection.py --arms A3 --limit 3        (ลองก่อน)
      python eval\\run_collection.py --resume eval\\results\\xxx.json
⚠ ต้องสตาร์ต Ollama ก่อน
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import translate                                                 # noqa: E402
from a1 import A1                                                # noqa: E402
from a3 import A3                                                # noqa: E402
from a3c import A3C                                              # noqa: E402
from embed import OLLAMA_URL                                     # noqa: E402
from eval.collection import (GROUP1_IN_DOMAIN, GROUP3_OUT_OF_DOMAIN,  # noqa: E402
                             GROUP4_BUDGET)
from eval.collection_th import thai_query                        # noqa: E402

# mark7 มี 3 แขน — แยกตัวแปรได้ทีละตัว
#   A1   RAG มาตรฐาน   ไม่มีลูป
#   A3C  Iterative RAG  มีลูป · **โค้ด**ตัดสินว่าจะวน
#   A3   Agentic RAG    มีลูป · **LLM** ตัดสินว่าจะวน
# คู่ A3C <-> A3 ต่างกันฟังก์ชันเดียว จึงตอบได้ว่า "ใครควรคุมลูป"
ARMS = {"A1": A1, "A3C": A3C, "A3": A3}
RESULTS_DIR = ROOT / "eval" / "results"


def check_ollama() -> None:
    import httpx
    try:
        httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10).raise_for_status()
    except Exception as exc:                                     # noqa: BLE001
        raise SystemExit(f"❌ ต่อ Ollama ที่ {OLLAMA_URL} ไม่ได้ — "
                         f"สตาร์ตด้วย `ollama.exe serve`\n   {exc}") from exc


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(path)


def run_one(arm, q: str) -> dict:
    """ถามหนึ่งคำถาม เก็บทุกอย่างที่ตัวชี้วัดและการติดป้ายต้องใช้"""
    if hasattr(arm, "reset"):
        arm.reset()
    t0 = time.perf_counter()
    turn = arm.respond(q)
    seconds = time.perf_counter() - t0
    t = turn.trace
    gen = t.get("generator") or {}
    rr = t.get("rerank") or {}
    return {
        # สำหรับติดป้าย ก (ความตรงของสินค้า)
        "picked": [{"id": h.id, "title": h.title, "price": h.price,
                    "store": h.store, "category": h.category,
                    "score": round(h.score, 4)} for h in turn.hits],
        # สำหรับติดป้าย ข (ความซื่อตรงของคำตอบ)
        "reply": turn.reply,
        "context": gen.get("context", ""),
        "weak": bool(gen.get("weak", False)),
        "llm_wrote": not bool(gen.get("weak", False)) and bool(turn.hits),
        # ตัวชี้วัดที่ไม่ต้องใช้ป้าย
        "n_products": gen.get("n_products", len(turn.hits)),
        "n_passed": rr.get("n_passed"),
        "n_candidates": rr.get("n_candidates"),
        "n_searches": t.get("n_searches", 1),
        # ⚠ คำค้นที่ระบบใช้จริง — ต่างจากคำที่ผู้ใช้พิมพ์ เพราะผ่านชั้นความจำ
        # และชั้นแปล · บั๊ก "ชั้นความจำตัดคำผู้ใช้ทิ้ง" เจอได้เพราะเปิดดูตรงนี้
        "tried_queries": t.get("tried_queries", []),
        "search_texts": [r.get("search_text") for r in (t.get("rounds") or [])
                         if isinstance(r, dict)],
        "llm_calls": t.get("llm_calls", 0),
        # ⚠ ช่องของลูปที่เพิ่มภายหลัง — เคยลืมเก็บแล้วทำให้วิเคราะห์ไม่ได้ว่า
        # action ใหม่ยิงข้อไหน ต้องเดาจากจำนวนครั้งที่เรียก LLM แทน
        "forced_by_word_match": t.get("forced_by_word_match", 0),
        "reranked_by": t.get("reranked_by", []),
        "word_match": t.get("word_match"),
        # ⚠ ใครตัดสินว่าจะวนลูป — A3C ต้องเป็น LLM 0 ครั้งเสมอ · A3 ต้องมากกว่า 0
        # (รอบอังกฤษ 2026-10-12 ลืมเก็บ 2 ช่องนี้ ข้อมูลรอบนั้นจึงไม่มี)
        "loop_by_llm": t.get("loop_by_llm", 0),
        "loop_by_code": t.get("loop_by_code", 0),
        "loop_decisions": t.get("loop_decisions", []),
        "stop_reason": t.get("stop_reason", ""),
        "seconds": round(seconds, 2),
        "budget_read": (t.get("memory") or {}).get("profile", {}).get("budget_max"),
        "unsupported_numbers": gen.get("unsupported_numbers", []),
        # ⚠ คำที่เหตุผลปฏิเสธ แต่มีอยู่ในชื่อสินค้า -> ตัวชี้วัดของขั้นที่ 163-165
        "contradicted": gen.get("contradicted", []),
        # ⚠ เหตุผลชิ้นที่โค้ดทิ้งเพราะเป็นคำค้นเปล่า ๆ -> ตัวชี้วัดของขั้นที่ 172
        # เก็บเป็นเลขลำดับชิ้น ทำให้รายงานได้ทั้งพฤติกรรมดิบของโมเดล
        # (นับ echoed) และผลหลังกรอง (อ่านจาก reply) จากการรันครั้งเดียว
        "echoed": gen.get("echoed", []),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="รันแขนบนชุดทดสอบที่ล็อกไว้")
    ap.add_argument("--arms", nargs="+", default=["A1", "A3C", "A3"], choices=list(ARMS))
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="จำกัดคำค้นต่อกลุ่ม (0 = ทั้งหมด)")
    ap.add_argument("--resume", type=Path, default=None)
    ap.add_argument("--lang", choices=["en", "th"], default="en",
                    help="th = ใช้คำค้นไทยจาก eval/collection_th.py (id เดิม ป้ายเดิมใช้ได้)")
    args = ap.parse_args()
    check_ollama()

    groups = {"g1": list(GROUP1_IN_DOMAIN), "g3": list(GROUP3_OUT_OF_DOMAIN),
              "g4": list(GROUP4_BUDGET)}
    if args.lang == "th":
        # ⚠ สลับเฉพาะ `q` · `id` คงเดิม -> ป้ายที่ติดไว้แล้วจับคู่ได้เหมือนเดิม
        # กลุ่ม 3 ที่แปลไม่ได้ (ชื่อคน/หนังสือ) จะคงเป็นอังกฤษ ซึ่งตั้งใจ
        groups = {g: [{**x, "q_en": x["q"], "q": thai_query(g, x["id"], x["q"])}
                      for x in items] for g, items in groups.items()}
    if args.limit:
        groups = {k: v[:args.limit] for k, v in groups.items()}
    total_q = sum(len(v) for v in groups.values())

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    tag = "" if args.lang == "en" else f"_{args.lang}"
    out = RESULTS_DIR / f"collection{tag}_{stamp}.json"
    raw: dict = {}
    if args.resume and args.resume.exists():
        raw = json.loads(args.resume.read_text(encoding="utf-8")).get("raw", {})
        done = sum(len(r) for a in raw.values() for r in a.values())
        print(f"กู้ต่อจาก {args.resume.name} — ทำไปแล้ว {done} ข้อ")

    payload = {"when": stamp, "arms": args.arms, "rounds": args.rounds,
               "lang": args.lang,
               "n_queries": {k: len(v) for k, v in groups.items()}, "raw": raw}

    print(f"ภาษา {args.lang} · แขน {', '.join(args.arms)} · คำค้น {total_q} "
          f"(g1 {len(groups['g1'])} · g3 {len(groups['g3'])} · g4 {len(groups['g4'])}) "
          f"· {args.rounds} รอบ")
    print(f"รวม {total_q * len(args.arms) * args.rounds} การตอบ · "
          f"ประมาณ {total_q * len(args.arms) * args.rounds * 19 / 3600:.1f} ชม.\n")

    t_start = time.perf_counter()
    done_n = 0
    failed: list[tuple[str, str, str]] = []
    for rnd in range(1, args.rounds + 1):
        for name in args.arms:
            key = f"{name}_r{rnd}"
            raw.setdefault(key, {})
            # ⚠ ล้างคำแปลที่จำไว้ ไม่งั้นรอบหลังได้ของฟรีจากรอบก่อน
            translate.clear_cache()
            with ARMS[name]() as arm:
                for gname, items in groups.items():
                    bucket = raw[key].setdefault(gname, {})
                    for item in items:
                        if item["id"] in bucket:
                            done_n += 1
                            continue
                        # ⚠ **การเรียกครั้งเดียวค้าง ต้องไม่ล้มทั้งการรัน**
                        # เกิดมาแล้ว 3 ครั้ง ครั้งล่าสุดเสียงาน 121 ข้อของรอบ 2
                        # บันทึกว่าข้อนี้พังแล้วไปต่อ · `--resume` จะกลับมาทำซ้ำ
                        # เพราะข้อที่มี "error" ถือว่ายังไม่เสร็จ
                        try:
                            bucket[item["id"]] = {"q": item["q"],
                                                  **run_one(arm, item["q"])}
                        except Exception as exc:                 # noqa: BLE001
                            failed.append((key, item["id"], type(exc).__name__))
                            print(f"  ⚠ {key}/{item['id']} พัง "
                                  f"({type(exc).__name__}) — ข้ามไปก่อน")
                        save(out, payload)
                        done_n += 1
                        if done_n % 10 == 0:
                            el = time.perf_counter() - t_start
                            tot = total_q * len(args.arms) * args.rounds
                            print(f"  {done_n}/{tot} · ผ่านไป {el/60:.0f} น. · "
                                  f"เหลือราว {el/max(done_n,1)*(tot-done_n)/60:.0f} น.")
            print(f"-- {key} เสร็จ")

    payload["elapsed_min"] = round((time.perf_counter() - t_start) / 60, 1)
    payload["failed"] = [{"round": k, "qid": q, "error": e} for k, q, e in failed]
    save(out, payload)
    if failed:
        print(f"\n⚠ มี {len(failed)} ข้อที่พังและถูกข้าม — "
              f"รัน --resume อีกรอบเพื่อทำซ้ำ")
        for k, q, e in failed[:10]:
            print(f"    {k}/{q}  {e}")
    print(f"\nเสร็จใน {payload['elapsed_min']:.0f} นาที · บันทึกที่ {out.relative_to(ROOT)}")
    print(f"ถ้าตายกลางทาง: python eval\\run_collection.py --resume {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
