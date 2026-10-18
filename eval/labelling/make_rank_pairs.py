r"""สร้างไฟล์ป้าย ก สำหรับ**ของที่โผล่ใหม่หลังเปลี่ยนตัวจัดอันดับ**

**ทำไมต้องมี** ตัวจัดอันดับเปลี่ยน (สัญญาณคำซ้อน + ข้อกำหนดที่ขาดไม่ได้)
→ คำค้นเดิม กอง 100 ชิ้นเดิม **แต่หยิบของคนละชิ้นขึ้น 3 อันดับแรก**
ของที่โผล่ใหม่ไม่มีป้าย `metrics_labelled.py` จึง**ตัดคำค้นนั้นทิ้งทั้งข้อ**
เหลือชุดคำค้นร่วมแค่ 21/50 และ 19 ใน 21 นั้นทุกแขนได้ผลเหมือนกันเป๊ะ
→ **วัดอะไรไม่ได้** (pooling bias · Zobel 1998 · docs/steps.md ข้อ 298-306)

## 🔑 ไฟล์นี้ปิดตาคนติดป้าย

**ไม่บอกว่าแขนไหนหยิบของชิ้นนี้ขึ้นมา** และเรียงแถวด้วยค่าแฮชที่คงที่
ไม่ใช่เรียงตามแขนหรือตามคำค้น เพราะถ้าคนติดป้ายรู้ว่าชิ้นนี้มาจาก A3C
ป้ายจะเอนไปตามความคาดหวังว่าแขนไหนควรชนะ — ซึ่งเป็นผลที่โปรเจกต์นี้
กำลังพยายามวัดอยู่พอดี · ต้องการย้อนดูว่าแขนไหนหยิบ ให้ join ด้วย (qid, ชื่อสินค้า)
จากไฟล์ผลภายหลัง

ป้าย 4 ระดับตาม ESCI (Reddy et al. 2022) เหมือนไฟล์ `labels_a*.csv` เดิม
    3 = ตรงเป๊ะ   2 = ใช้แทนได้   1 = เกี่ยวข้องแต่ใช้แทนไม่ได้   0 = ไม่เกี่ยว

รัน:  .venv\Scripts\python.exe eval\labelling\make_rank_pairs.py en
      .venv\Scripts\python.exe eval\labelling\make_rank_pairs.py th
"""
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

DETAIL_CHARS = 300
ARMS = ("A1_r1", "A3C_r1", "A3_r1")

# ชุดไฟล์ผลของการรันหลังเปลี่ยนตัวจัดอันดับ
RUNS = {
    "en": ("collection_20261017_1213.json", "labels_a9_rank_en.csv", "en"),
    "th": ("collection_th_20261017_1350.json", "labels_a9_rank_th.csv", "th"),
}
NEED = 140          # g1 50 + g3 60 + g4 30 — ต้องครบก่อนจึงจะสร้างไฟล์ป้ายได้


def existing_labels() -> set[tuple[str, str]]:
    """คู่ (คำค้น, ชื่อสินค้า) ที่มีป้ายแล้วในไฟล์ labels_a*.csv ทุกไฟล์"""
    out = set()
    for path in sorted((ROOT / "eval/labels").glob("labels_a*.csv")):
        if path.name.endswith(("_check.csv", "_pilot.csv")):
            continue
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if (r.get("label") or "").strip():
                    out.add((r["qid"], r["product_title"]))
    return out


def query_text(lang: str) -> tuple[dict[str, str], dict[str, str]]:
    """(คำค้นอังกฤษตามรหัส, คำค้นไทยตามรหัส) — ไฟล์ป้ายเก็บทั้งสองคอลัมน์"""
    from eval.collection import (GROUP1_IN_DOMAIN, GROUP3_OUT_OF_DOMAIN,
                                 GROUP4_BUDGET)
    en = {x["id"]: x["q"] for grp in
          (GROUP1_IN_DOMAIN, GROUP3_OUT_OF_DOMAIN, GROUP4_BUDGET) for x in grp}
    th: dict[str, str] = {}
    if lang == "th":
        from eval.collection_th import GROUP1_TH, GROUP3_TH, GROUP4_TH
        for table in (GROUP1_TH, GROUP3_TH, GROUP4_TH):
            th.update(table)
    return en, th


def add_details(rows: list[dict]) -> int:
    """เติมคำบรรยายสินค้าจากคลัง — ดึงด้วยรหัสสินค้า **ไม่เรียก Ollama**
    จึงรันพร้อมกับการประเมินได้ ไม่แย่งทรัพยากร"""
    try:
        from retrieval import Retriever
    except Exception:                                            # noqa: BLE001
        return 0
    n = 0
    try:
        with Retriever() as rt:
            for r in rows:
                hit = rt.get(r.pop("_id"))
                if hit is not None and hit.document:
                    r["details"] = " ".join(hit.document[:DETAIL_CHARS].split())
                    n += 1
    except Exception as exc:                                     # noqa: BLE001
        print(f"  ⚠ ต่อคลังไม่ได้ ({type(exc).__name__}) — ไฟล์จะไม่มีคำบรรยาย")
    for r in rows:
        r.pop("_id", None)
    return n


def main() -> None:
    if (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    lang = (sys.argv[1] if len(sys.argv) > 1 else "en").lower()
    if lang not in RUNS:
        sys.exit(__doc__)
    res_file, out_name, _ = RUNS[lang]
    if res_file is None:
        sys.exit(f"ยังไม่ได้ตั้งชื่อไฟล์ผลของภาษา {lang} ใน RUNS — "
                 f"รันประเมินให้จบก่อนแล้วมาเติม")

    raw = json.loads((ROOT / "eval/results" / res_file).read_text(encoding="utf-8"))["raw"]

    # ⚠ กันสร้างไฟล์ป้ายจากผลที่ยังรันไม่จบ — ถ้าสร้างตอนรันได้ครึ่งทาง
    # จะได้ไฟล์ที่ขาดคู่ แล้วพอรันจบจะสร้างทับไม่ได้ (โค้ดกันเขียนทับไว้)
    short = {a: sum(len(v) for v in raw.get(a, {}).values()) for a in ARMS}
    if any(n < NEED for n in short.values()):
        sys.exit("⚠ ผลยังรันไม่ครบ — " + " · ".join(
            f"{a} {n}/{NEED}" for a, n in short.items()) + "\n   รอให้จบก่อน")

    have = existing_labels()
    en_q, th_q = query_text(lang)

    # เก็บคู่ที่ยังไม่มีป้าย · ตัดซ้ำด้วย (รหัสคำค้น, ชื่อสินค้า)
    seen: dict[tuple[str, str], dict] = {}
    for arm in ARMS:
        for group in raw.get(arm, {}).values():
            for qid, rec in group.items():
                for p in (rec.get("picked") or [])[:3]:
                    key = (qid, p["title"])
                    if key in have or key in seen:
                        continue
                    seen[key] = {
                        "_id": p["id"],
                        "pair_id": "",
                        "qid": qid,
                        "query": en_q.get(qid, ""),
                        "query_th": th_q.get(qid, ""),
                        "product_title": p["title"],
                        "category": p.get("category", ""),
                        "price": p.get("price", ""),
                        "store": p.get("store", ""),
                        "details": "",
                        "label": "",
                        "note": "",
                    }

    # 🔑 เรียงด้วยแฮชที่คงที่ — ปิดตา ไม่เรียงตามแขนหรือตามคำค้น
    rows = sorted(seen.values(), key=lambda r: hashlib.sha1(
        f'{r["qid"]}|{r["product_title"]}'.encode()).hexdigest())
    for i, r in enumerate(rows, 1):
        r["pair_id"] = f"a9{lang}{i:03d}"

    filled = add_details(rows)
    out = ROOT / "eval/labels" / out_name
    if out.exists():
        sys.exit(f"⚠ {out.name} มีอยู่แล้ว — ลบหรือเปลี่ยนชื่อก่อน "
                 f"ไม่เขียนทับเพราะอาจมีป้ายที่ติดไว้แล้ว")
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"เขียน {out.name} · {len(rows)} คู่ที่ต้องติดป้าย · "
          f"เติมคำบรรยายได้ {filled}/{len(rows)}")
    print(f"กระทบ {len({r['qid'] for r in rows})} คำค้น · "
          f"ปิดตาแล้ว (ไม่บอกว่าแขนไหนหยิบ · เรียงด้วยแฮช)")
    print(f"\nดูรายละเอียดเพื่อติดป้าย:  "
          f".venv\\Scripts\\python.exe eval\\labelling\\show_rank.py {lang} 1 10")


if __name__ == "__main__":
    main()
