"""สร้างไฟล์ให้คนติดป้าย จากผลรันใน `eval/results/`

**กองที่ต้องติดป้ายสร้างแบบ TREC pooling** (Voorhees & Harman 2005) — รวมสินค้าที่
*ทุกแขน ทุกรอบ* หยิบมาเป็นกองเดียว แล้วติดป้ายครั้งเดียว ป้ายชุดนั้นใช้ได้กับทุกแขน
ถ้าติดป้ายแยกรายแขน แขนที่ติดทีหลังจะได้เปรียบเพราะคนติดเริ่มคุ้นกับคำค้นแล้ว

**ติดแบบปิดตา** — ไฟล์ไม่มีคอลัมน์บอกแขน รอบ อันดับ หรือคะแนน และสลับลำดับสินค้า
ในแต่ละคำค้นด้วยเมล็ดสุ่มคงที่ (ทำซ้ำได้) เพื่อไม่ให้เดาได้ว่าระบบจัดอันดับไว้อย่างไร

สร้าง 4 ไฟล์
  labels_a.csv        ป้าย ก — ความตรงของสินค้า (เกณฑ์ ESCI)  <- กองใหญ่
  labels_a_pilot.csv  20 คู่แรกไว้ติดนำร่องก่อน แล้ววัดความสอดคล้องกับคู่มือ
  labels_b.csv        ป้าย ข — ความซื่อตรงของคำตอบ (ช่องให้กรอก)
  labels_b_read.md    ป้าย ข ฉบับอ่านสบาย (ข้อเท็จจริง + คำตอบ คู่กัน)

รัน:  python eval\\make_labels.py eval\\results\\collection_20261003_2039.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.collection import GROUP1_IN_DOMAIN                     # noqa: E402

OUT_DIR = ROOT / "eval" / "labels"
SEED = 20261003          # เมล็ดสุ่มคงที่ -> สลับลำดับซ้ำได้เหมือนเดิมทุกครั้ง
PILOT_N = 20             # ติดนำร่องก่อนเท่านี้คู่ (docs/eval_plan.md ข้อ 5.5)
ANSWERS_N = 15           # ป้าย ข ติดกี่คำตอบ
DETAIL_CHARS = 300

BAND = {x["id"]: x["band"] for x in GROUP1_IN_DOMAIN}


def pool_products(raw: dict) -> dict[str, dict[str, dict]]:
    """รวมสินค้าที่ถูกหยิบใน**ทุกแขน ทุกรอบ** ของคำค้นกลุ่ม 1

    คืน {qid: {product_id: ข้อมูลสินค้า}} — ใช้ dict กัน id ซ้ำโดยอัตโนมัติ
    """
    pool: dict[str, dict[str, dict]] = {}
    for arm_round in raw.values():
        for qid, rec in arm_round.get("g1", {}).items():
            bucket = pool.setdefault(qid, {})
            for p in rec["picked"]:
                bucket.setdefault(p["id"], {**p, "q": rec["q"]})
    return pool


def add_details(pool: dict) -> int:
    """เติมคำบรรยายสินค้าจากคลัง — คนติดป้ายต้องเห็นมากกว่าแค่ชื่อ

    ถ้าต่อคลังไม่ได้ ยังสร้างไฟล์ได้ แต่คุณภาพป้ายจะแย่ลง จึงบอกจำนวนที่เติมได้
    """
    try:
        from retrieval import Retriever
    except Exception:                                            # noqa: BLE001
        return 0
    n = 0
    try:
        with Retriever() as rt:
            for products in pool.values():
                for pid, p in products.items():
                    hit = rt.get(pid)
                    if hit is not None and hit.document:
                        p["details"] = " ".join(
                            hit.document[:DETAIL_CHARS].split())
                        n += 1
    except Exception as exc:                                     # noqa: BLE001
        print(f"  ⚠ ต่อคลังไม่ได้ ({type(exc).__name__}) — ไฟล์จะไม่มีคำบรรยาย")
    return n


# ⚠ **ไม่มีคอลัมน์ `band`** — ชั้นความยากมาจากคะแนนที่ *ระบบ* ให้ไว้
# ถ้าคนติดป้ายเห็นว่าคำนี้ "ยาก" จะตั้งความคาดหวังไว้ต่ำแล้วให้คะแนนใจดีขึ้น
# ซึ่งคือการให้ระบบมีอิทธิพลต่อเฉลยของตัวเอง · ชั้นความยากดูย้อนได้จาก
# `eval/collection.py` ตอนวิเคราะห์ โดยจับคู่ด้วย `qid`
# เหตุผลเดียวกับที่ไม่มีคอลัมน์ แขน · รอบ · อันดับ · คะแนน
FIELDS_A = ["pair_id", "qid", "query", "product_title", "category",
            "price", "store", "details", "label", "note"]


def write_a(pool: dict, path: Path, pilot: Path) -> tuple[int, int]:
    rng = random.Random(SEED)
    rows = []
    for qid in sorted(pool):
        items = list(pool[qid].values())
        rng.shuffle(items)                 # ⚠ กันการเดาอันดับที่ระบบให้ไว้
        for p in items:
            rows.append({
                "pair_id": "", "qid": qid,
                "query": p["q"], "product_title": p["title"],
                "category": p.get("category", ""),
                "price": "" if p.get("price") is None else p["price"],
                "store": p.get("store", ""), "details": p.get("details", ""),
                "label": "", "note": ""})
    for i, r in enumerate(rows, 1):
        r["pair_id"] = f"a{i:03d}"

    def dump(target: Path, data: list[dict]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        # utf-8-sig เพื่อให้ Excel บน Windows อ่านภาษาไทยไม่เพี้ยน
        with target.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS_A)
            w.writeheader()
            w.writerows(data)

    dump(path, rows)
    # กองนำร่อง: **แบ่งโควตาตามชั้นความยาก** ไม่ใช่สุ่มล้วน
    # สุ่มล้วนได้คำค้นชั้นยากแค่ 2/20 ซึ่งเป็นชั้นที่คู่มือมักกำกวมที่สุด
    # (โค้ดใช้ band ได้ แต่ไฟล์ที่คนเห็นไม่มีคอลัมน์นี้)
    prng = random.Random(SEED + 1)
    by_band: dict[str, list[dict]] = {}
    for r in rows:
        by_band.setdefault(BAND.get(r["qid"], "—"), []).append(r)
    quota = PILOT_N // max(len(by_band), 1)
    picked: list[dict] = []
    for band in sorted(by_band):
        picked += prng.sample(by_band[band], min(quota, len(by_band[band])))
    rest = [r for r in rows if r not in picked]
    picked += prng.sample(rest, min(PILOT_N - len(picked), len(rest)))
    picked.sort(key=lambda r: r["pair_id"])
    dump(pilot, picked)
    return len(rows), len({r["qid"] for r in rows})


FIELDS_B = ["ans_id", "qid", "query", "n_products", "label", "kind", "note"]


def write_b(raw: dict, csv_path: Path, md_path: Path) -> int:
    """เลือกคำตอบมาติดป้ายความซื่อตรง — **กรองโหมดอ่อนออก**

    โหมดอ่อนโค้ดเขียนเองทั้งก้อน จึงซื่อตรง 100% โดยโครงสร้าง
    ถ้านับรวมจะเป็นการให้คะแนนฟรี (docs/eval_plan.md ข้อ 4 ส่วน ข)
    """
    first = raw[sorted(raw)[0]]                 # ใช้รอบแรกเป็นตัวแทน
    pool = [(qid, r) for qid, r in first.get("g1", {}).items()
            if r["picked"] and not r["weak"] and r["context"]]
    pool.sort()
    chosen = random.Random(SEED + 2).sample(pool, min(ANSWERS_N, len(pool)))
    chosen.sort()

    rows, md = [], ["# ป้าย ข — ความซื่อตรงของคำตอบ (ฉบับอ่าน)", "",
                    "อ่านไฟล์นี้ แล้วกรอกคะแนนลง `labels_b.csv` โดยใช้ `ans_id` จับคู่กัน",
                    "", "เกณฑ์: **2** ทุกข้อความมีข้อมูลรองรับ · **1** ขยายความเกินนิดหน่อยแต่ไม่ผิด"
                    " · **0** มีข้อความที่ข้อมูลไม่รองรับหรือขัดกับข้อมูล", "",
                    "ถ้าให้ 0 หรือ 1 ระบุชนิดด้วย: `intrinsic` บิดเบือนข้อมูลที่ให้ ·"
                    " `extrinsic` เติมสิ่งที่ไม่มีในข้อมูล", "", "---", ""]
    for i, (qid, r) in enumerate(chosen, 1):
        aid = f"b{i:02d}"
        rows.append({"ans_id": aid, "qid": qid, "query": r["q"],
                     "n_products": len(r["picked"]), "label": "",
                     "kind": "", "note": ""})
        md += [f"## {aid}", "", f'**ผู้ใช้ถาม:** {r["q"]}', "",
               "**ข้อเท็จจริงที่ระบบมีอยู่ในมือ**", "", "```",
               r["context"], "```", "",
               "**คำตอบที่ระบบเขียน**", "", "```", r["reply"], "```", "",
               f"ให้คะแนน `{aid}` = ____   ชนิด = ____", "", "---", ""]

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS_B)
        w.writeheader()
        w.writerows(rows)
    md_path.write_text("\n".join(md), encoding="utf-8")
    return len(rows)


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="สร้างไฟล์ให้คนติดป้าย")
    ap.add_argument("results", type=Path)
    args = ap.parse_args()

    raw = json.loads(args.results.read_text(encoding="utf-8"))["raw"]
    print(f"อ่านผลจาก {len(raw)} แขน-รอบ: {', '.join(sorted(raw))}")

    pool = pool_products(raw)
    n_pairs = sum(len(v) for v in pool.values())
    print(f"\nกอง pooling — คำค้นกลุ่ม 1 จำนวน {len(pool)} คำ · สินค้าไม่ซ้ำ {n_pairs} คู่")
    print(f"  ถ้าไม่รวมของซ้ำข้ามรอบจะเป็น "
          f"{sum(len(r['picked']) for a in raw.values() for r in a.get('g1', {}).values())} คู่"
          f" -> **pooling ประหยัดไป "
          f"{sum(len(r['picked']) for a in raw.values() for r in a.get('g1', {}).values()) - n_pairs} คู่**")

    print("\nกำลังเติมคำบรรยายสินค้าจากคลัง...")
    print(f"  เติมได้ {add_details(pool)}/{n_pairs} คู่")

    n, nq = write_a(pool, OUT_DIR / "labels_a.csv", OUT_DIR / "labels_a_pilot.csv")
    nb = write_b(raw, OUT_DIR / "labels_b.csv", OUT_DIR / "labels_b_read.md")

    print(f"\nสร้างไฟล์แล้วที่ {OUT_DIR.relative_to(ROOT)}\\")
    print(f"  labels_a.csv        {n} คู่ จาก {nq} คำค้น   <- กองใหญ่")
    print(f"  labels_a_pilot.csv  {min(PILOT_N, n)} คู่ (คละชั้นความยาก) <- ติดก่อน")
    print(f"  labels_b.csv        {nb} คำตอบ")
    print(f"  labels_b_read.md    ฉบับอ่านคู่กับ labels_b.csv")
    print(f"\nคู่มือติดป้าย: docs/labelling_guide.md")


if __name__ == "__main__":
    main()
