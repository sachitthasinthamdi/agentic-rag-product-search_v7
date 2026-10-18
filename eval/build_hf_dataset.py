"""ประกอบชุดข้อมูลที่จะเผยแพร่บน HuggingFace จากไฟล์ภายในของโปรเจกต์

ผลลัพธ์อยู่ที่ `hf_upload/`
    queries.csv   คำค้น 140 คำ · อังกฤษ + ไทย + กลุ่ม + ชั้นความยาก + แหล่งที่มา
    qrels.csv     ป้ายความตรง 241 คู่ · (qid, product_id, label)
    answers.csv   ป้ายความซื่อตรงของคำตอบ 30 รายการ (อังกฤษ 15 + ไทย 15)
    LICENSES/     สัญญาอนุญาตต้นฉบับ (ดาวน์โหลดจาก repo ต้นทาง)
    NOTICE.md     ที่มาและการดัดแปลง (Apache-2.0 §4b บังคับ)
    README.md     dataset card

⚠ **ไฟล์ป้ายภายในไม่มีรหัสสินค้า** เพราะตัดออกตอนติดป้ายเพื่อปิดตา
ต้องกู้กลับด้วยการจับคู่ (qid, ชื่อสินค้า) กับไฟล์ผลรัน

⚠ **ไม่เผยแพร่ตัวคลังสินค้า** เผยแพร่เฉพาะรหัสสินค้ากับชื่อ เพื่อให้ตรวจย้อนได้
โดยไม่ต้องแจกจ่ายข้อมูลของคนอื่นซ้ำ

รัน:  python eval\\build_hf_dataset.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LAB = ROOT / "eval" / "labels"
OUT = ROOT / "hf_upload"
RESULTS = ROOT / "eval" / "results"

from eval.collection import (GROUP1_IN_DOMAIN, GROUP3_OUT_OF_DOMAIN,  # noqa: E402
                             GROUP4_BUDGET)
from eval.collection_th import GROUP1_TH, GROUP3_TH, GROUP4_TH        # noqa: E402


def product_ids() -> dict[tuple[str, str], str]:
    """กู้รหัสสินค้าจากไฟล์ผลรันทุกไฟล์ · คีย์ = (qid, ชื่อสินค้า)"""
    out = {}
    for f in sorted(RESULTS.glob("collection*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))["raw"]
        except Exception:                                        # noqa: BLE001
            continue
        # ⚠ ต้องวนทุกกลุ่ม — เดิมอ่านแค่ "g1" ทำให้หารหัสของป้ายในกลุ่ม g3/g4
        # ไม่เจอ 329 จาก 676 คู่ แล้วตัดทิ้งเงียบ ๆ (เจอ 17 ต.ค. 2026)
        for arm_round in raw.values():
            for group in arm_round.values():
                if not isinstance(group, dict):
                    continue
                for qid, rec in group.items():
                    for p in rec.get("picked", []):
                        out[(qid, p["title"])] = p["id"]
    return out


def write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  {path.relative_to(ROOT)}  {len(rows)} แถว")


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("ประกอบชุดข้อมูลสำหรับเผยแพร่")

    # ---- queries ----
    qrows = []
    for x in GROUP1_IN_DOMAIN:
        qrows.append({"qid": x["id"], "group": "in_domain", "query_en": x["q"],
                      "query_th": GROUP1_TH.get(x["id"], ""), "band": x["band"],
                      "source": x["src"], "budget_usd": "",
                      "needs_qrels": "yes"})
    for x in GROUP3_OUT_OF_DOMAIN:
        th = GROUP3_TH.get(x["id"], "")
        qrows.append({"qid": x["id"], "group": "out_of_domain", "query_en": x["q"],
                      "query_th": th, "band": "", "source": x["src"],
                      "budget_usd": "", "needs_qrels": "no"})
    base_id = {x["q"]: x["id"] for x in GROUP1_IN_DOMAIN}
    for x in GROUP4_BUDGET:
        qrows.append({"qid": x["id"], "group": "budget", "query_en": x["q"],
                      "query_th": GROUP4_TH.get(x["id"], ""),
                      "band": next(g["band"] for g in GROUP1_IN_DOMAIN
                                   if g["id"] == base_id[x["base_q"]]),
                      "source": next(g["src"] for g in GROUP1_IN_DOMAIN
                                     if g["id"] == base_id[x["base_q"]]),
                      "budget_usd": x["budget"], "needs_qrels": "no"})
    write(OUT / "queries.csv",
          ["qid", "group", "query_en", "query_th", "band", "source",
           "budget_usd", "needs_qrels"], qrows)

    # ---- qrels ----
    pid = product_ids()
    qrels, no_id = [], 0
    # ⚠ อ่านไฟล์ป้ายทุกไฟล์ (labels_a.csv · _a2 · _a3 ...) ยกเว้นกองนำร่อง
    # และกองตรวจของคนที่สอง ซึ่งเป็นคู่เดียวกับไฟล์หลักอยู่แล้ว
    for f in sorted(LAB.glob("labels_a*.csv")):
        if f.name.endswith(("_pilot.csv", "_check.csv")):
            continue
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if not r["label"].strip():
                    continue
                key = (r["qid"], r["product_title"])
                if key not in pid:
                    no_id += 1
                    continue
                qrels.append({"qid": r["qid"], "product_id": pid[key],
                              "label": r["label"],
                              "product_title": r["product_title"]})
    if no_id:
        print(f"  ⚠ หารหัสสินค้าไม่เจอ {no_id} คู่ — ไม่ใส่ลงไฟล์")
    write(OUT / "qrels.csv",
          ["qid", "product_id", "label", "product_title"], qrels)

    # ---- answers (ป้าย ข) ----
    #
    # ⚠ **ans_id ซ้ำกันข้ามไฟล์** — `f01`–`f49` ถูกใช้ซ้ำทุกรอบ เคยทำให้ป้ายรอบ 4
    # เขียนทับรอบ 3 ไป 34 แถวมาแล้ว (ดู eval/labelling/README.md กับดักข้อ 1)
    # ป้าย ข ผูกกับ **รอบ × แขน × ภาษา** ไม่ใช่กับคำค้นอย่างเดียว จึงต้องมีคอลัมน์
    # `round` กับ `arm` กำกับ ไม่งั้นเทรวมแล้วป้ายชนกันและใช้ไม่ได้เลย
    #
    # กุญแจที่ทำให้แถวไม่ซ้ำคือ (ans_id, qid, language, round, arm)
    B_FILES = (
        ("labels_b.csv",            1, "A3",  "en"),
        ("labels_b_th.csv",         1, "A3",  "th"),
        ("labels_b2.csv",           2, "A3",  "en"),
        ("labels_b2_th.csv",        2, "A3",  "th"),
        ("labels_b3.csv",           3, "A3",  "en"),
        ("labels_b3_th.csv",        3, "A3",  "th"),
        ("labels_b3_full.csv",      3, "A3",  "en"),
        ("labels_b3_full_a1.csv",   3, "A1",  "en"),
        ("labels_b3_full_a3c.csv",  3, "A3C", "en"),
        ("labels_b3_th_full.csv",   3, "A3",  "th"),
        ("labels_b4_th.csv",        4, "A3",  "th"),
        ("labels_b4_th_full.csv",   4, "A3",  "th"),
        ("labels_b4_th_a1.csv",     4, "A1",  "th"),
    )
    arows, seen = [], set()
    for name, rnd, arm, lang in B_FILES:
        f = LAB / name
        if not f.exists():
            print(f"  ⚠ ไม่มีไฟล์ {name} — ข้าม")
            continue
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if not r["label"].strip():
                    continue
                key = (r["ans_id"], r["qid"], lang, rnd, arm)
                if key in seen:
                    print(f"  ⚠ แถวซ้ำใน {name}: {key} — ข้าม")
                    continue
                seen.add(key)
                arows.append({"ans_id": r["ans_id"], "qid": r["qid"],
                              "language": lang, "round": rnd, "arm": arm,
                              "faithfulness": r["label"], "error_kind": r["kind"]})
    write(OUT / "answers.csv",
          ["ans_id", "qid", "language", "round", "arm",
           "faithfulness", "error_kind"], arows)

    from collections import Counter
    print(f"\nสรุป")
    print(f"  คำค้น {len(qrows)}  {dict(Counter(r['group'] for r in qrows))}")
    print(f"  แหล่งที่มา {dict(Counter(r['source'] for r in qrows if r['source']))}")
    print(f"  ป้ายความตรง {len(qrels)}  {dict(sorted(Counter(r['label'] for r in qrels).items()))}")
    print(f"  ป้ายคำตอบ {len(arows)}  {dict(Counter(r['language'] for r in arows))}")
    for extra in ("NOTICE.md", "LICENSES/ESCI-Apache-2.0.txt",
                  "LICENSES/WANDS-MIT.txt", "README.md"):
        mark = "✅" if (OUT / extra).exists() else "❌ ยังไม่มี"
        print(f"  {mark} {extra}")


if __name__ == "__main__":
    main()
