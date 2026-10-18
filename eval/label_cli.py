"""ติดป้ายผ่านการสนทนา แทนการกรอกใน Excel

ผู้ใช้บอกว่ากรอกใน Excel ยาก เครื่องมือนี้แสดงทีละไม่กี่คำค้นให้อ่าน แล้วรับป้าย
เป็นเลขสั้น ๆ **บันทึกลงไฟล์ CSV เดิมทันทีทุกครั้ง** ไม่เก็บไว้ในแชต
ถ้าแชตหายหรือเครื่องดับ ป้ายที่ติดไปแล้วยังอยู่ครบ

⚠ **ยังปิดตาเหมือนเดิม** — แสดงตามลำดับที่สลับไว้แล้วใน CSV และไม่แสดง
แขน · รอบ · อันดับ · คะแนน · ชั้นความยาก เหมือนที่ตัดออกจากไฟล์

คำสั่ง
    show  <ไฟล์> [--n 3]              แสดงคำค้นถัดไปที่ยังไม่ได้ติด
    set   <ไฟล์> a001=3 a002=2 ...    บันทึกป้าย (ใส่หมายเหตุด้วย a003=2:ไม่แน่ใจ)
    stat  <ไฟล์>                      ดูว่าติดไปแล้วเท่าไหร่
    sync  <ต้นทาง> <ปลายทาง>          คัดลอกป้ายจากไฟล์นำร่องไปไฟล์ใหญ่ (จับคู่ด้วย pair_id)
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

ENC = "utf-8-sig"
VALID = {"3", "2", "1", "0"}
MEAN = {"3": "ตรงเป๊ะ", "2": "ใช้แทนได้", "1": "ของใช้คู่กัน", "0": "ไม่เกี่ยว"}
DETAIL_SHOW = 150


def load(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(encoding=ENC, newline="") as fh:
        r = csv.DictReader(fh)
        return list(r), list(r.fieldnames or [])


def save(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding=ENC, newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def done(rows: list[dict]) -> int:
    return sum(1 for r in rows if r["label"].strip())


def cmd_show(path: Path, n: int) -> None:
    rows, _ = load(path)
    todo = [r for r in rows if not r["label"].strip()]
    if not todo:
        print(f"ติดครบแล้วทั้ง {len(rows)} คู่ 🎉")
        return
    # จัดกลุ่มตามคำค้น แล้วเอามา n คำค้น — อ่านของคำเดียวกันติดกันทำให้มาตรฐานนิ่ง
    order, groups = [], {}
    for r in todo:
        if r["qid"] not in groups:
            groups[r["qid"]] = []
            order.append(r["qid"])
        groups[r["qid"]].append(r)

    print(f"เหลือ {len(todo)} คู่ จาก {len(rows)} · แสดง {min(n, len(order))} คำค้นถัดไป\n")
    ids = []
    for qid in order[:n]:
        items = groups[qid]
        print("=" * 78)
        print(f'ผู้ใช้ค้นหา:  "{items[0]["query"]}"')
        if items[0].get("query_th"):
            print(f'   (ภาษาไทย: "{items[0]["query_th"]}")')
        print("=" * 78)
        for r in items:
            ids.append(r["pair_id"])
            price = f'${r["price"]}' if r["price"] else "ไม่ระบุราคา"
            print(f'\n  [{r["pair_id"]}]  {r["product_title"]}')
            print(f'          {price} · {r["store"]} · {r["category"]}')
            if r["details"]:
                print(f'          {r["details"][:DETAIL_SHOW]}')
        print()
    print("-" * 78)
    print("ตอบกลับเป็นเลขเรียงตามลำดับที่แสดง  3=ตรงเป๊ะ 2=ใช้แทนได้ 1=ของใช้คู่กัน 0=ไม่เกี่ยว")
    print(f"ลำดับที่ถาม: {' '.join(ids)}")


def cmd_set(path: Path, pairs: list[str]) -> None:
    rows, fields = load(path)
    index = {r["pair_id"]: r for r in rows}
    ok, bad = [], []
    for item in pairs:
        if "=" not in item:
            bad.append(f"{item} (ไม่มีเครื่องหมาย =)")
            continue
        pid, _, val = item.partition("=")
        label, _, note = val.partition(":")
        pid, label = pid.strip(), label.strip()
        if pid not in index:
            bad.append(f"{item} (ไม่มี pair_id นี้)")
        elif label not in VALID:
            bad.append(f"{item} (ป้ายต้องเป็น 3/2/1/0)")
        else:
            index[pid]["label"] = label
            if note.strip():
                index[pid]["note"] = note.strip()
            ok.append((pid, label))
    save(path, rows, fields)
    for pid, label in ok:
        print(f"  {pid} = {label} ({MEAN[label]})")
    for b in bad:
        print(f"  ❌ {b}")
    print(f"\nบันทึกแล้ว {len(ok)} คู่ · รวมติดไปแล้ว {done(rows)}/{len(rows)}")


# ---------------------------------------------------------------------------
# ป้าย ข — ความซื่อตรงของคำตอบ · คนละสเกลกับป้าย ก (2/1/0 ไม่ใช่ 3/2/1/0)
# ---------------------------------------------------------------------------

VALID_B = {"2", "1", "0"}
MEAN_B = {"2": "ซื่อตรงทุกข้อความ", "1": "ขยายความเกินนิดหน่อย",
          "0": "มีข้อความที่ข้อมูลไม่รองรับ"}
KINDS = {"intrinsic", "extrinsic", ""}


def cmd_showb(path: Path, results: Path, n: int) -> None:
    """แสดงคำตอบที่ยังไม่ติดป้าย พร้อมข้อเท็จจริงที่ป้อนให้โมเดล"""
    rows, _ = load(path)
    todo = [r for r in rows if not r["label"].strip()]
    if not todo:
        print(f"ติดครบแล้วทั้ง {len(rows)} คำตอบ 🎉")
        return
    import json
    raw = json.loads(results.read_text(encoding="utf-8"))["raw"]
    first = raw[sorted(raw)[0]]["g1"]
    print(f"เหลือ {len(todo)} คำตอบ จาก {len(rows)} · แสดง {min(n, len(todo))}\n")
    for r in todo[:n]:
        rec = first[r["qid"]]
        print("=" * 78)
        print(f'[{r["ans_id"]}]  ผู้ใช้ถาม: "{r["q" if "q" in r else "query"]}"')
        print("=" * 78)
        print("--- ข้อเท็จจริงที่ระบบมีอยู่ในมือ ---")
        print(rec["context"])
        print("\n--- คำตอบที่ระบบเขียนให้ผู้ใช้ ---")
        print(rec["reply"])
        print()
    print("-" * 78)
    print("ป้าย: 2=ซื่อตรงทุกข้อความ 1=ขยายความเกินนิดหน่อย 0=มีข้อความที่ข้อมูลไม่รองรับ")
    print("ถ้าให้ 0 หรือ 1 ระบุชนิด: intrinsic=บิดเบือนข้อมูลที่ให้ · extrinsic=เติมสิ่งที่ไม่มี")
    print(f"ลำดับที่ถาม: {' '.join(r['ans_id'] for r in todo[:n])}")


def cmd_setb(path: Path, pairs: list[str]) -> None:
    rows, fields = load(path)
    index = {r["ans_id"]: r for r in rows}
    ok, bad = [], []
    for item in pairs:
        aid, _, val = item.partition("=")
        label, _, kind = val.partition(":")
        aid, label, kind = aid.strip(), label.strip(), kind.strip()
        if aid not in index:
            bad.append(f"{item} (ไม่มี ans_id นี้)")
        elif label not in VALID_B:
            bad.append(f"{item} (ป้ายต้องเป็น 2/1/0)")
        elif kind not in KINDS:
            bad.append(f"{item} (ชนิดต้องเป็น intrinsic หรือ extrinsic)")
        else:
            index[aid]["label"] = label
            index[aid]["kind"] = kind
            ok.append((aid, label, kind))
    save(path, rows, fields)
    for aid, label, kind in ok:
        print(f"  {aid} = {label} ({MEAN_B[label]}){' · ' + kind if kind else ''}")
    for b in bad:
        print(f"  ❌ {b}")
    n = sum(1 for r in rows if r["label"].strip())
    print(f"\nบันทึกแล้ว {len(ok)} คำตอบ · รวมติดไปแล้ว {n}/{len(rows)}")


def cmd_stat(path: Path) -> None:
    rows, _ = load(path)
    labels = [r["label"].strip() for r in rows if r["label"].strip()]
    print(f"{path.name}: ติดแล้ว {len(labels)}/{len(rows)}")
    if labels:
        c = Counter(labels)
        for k in ("3", "2", "1", "0"):
            n = c.get(k, 0)
            bar = "█" * round(n / len(labels) * 36)
            print(f"  {k} {MEAN[k]:<14}{n:>4}  {n / len(labels) * 100:4.0f}%  {bar}")
    marked = [r["pair_id"] for r in rows if "?" in r.get("note", "")]
    if marked:
        print(f"  ทำเครื่องหมายไว้ทบทวน: {', '.join(marked)}")


def cmd_sync(src: Path, dst: Path) -> None:
    s, _ = load(src)
    d, fields = load(dst)
    have = {r["pair_id"]: r for r in s if r["label"].strip()}
    n = 0
    for r in d:
        got = have.get(r["pair_id"])
        if got and not r["label"].strip():
            r["label"], r["note"] = got["label"], got.get("note", "")
            n += 1
    save(dst, d, fields)
    print(f"คัดลอกป้าย {n} คู่ จาก {src.name} ไป {dst.name} · "
          f"ตอนนี้ {dst.name} ติดแล้ว {done(d)}/{len(d)}")


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="ติดป้ายผ่านการสนทนา")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("show"); p.add_argument("file", type=Path); p.add_argument("--n", type=int, default=3)
    p = sub.add_parser("set"); p.add_argument("file", type=Path); p.add_argument("pairs", nargs="+")
    p = sub.add_parser("stat"); p.add_argument("file", type=Path)
    p = sub.add_parser("sync"); p.add_argument("src", type=Path); p.add_argument("dst", type=Path)
    p = sub.add_parser("showb"); p.add_argument("file", type=Path)
    p.add_argument("results", type=Path); p.add_argument("--n", type=int, default=3)
    p = sub.add_parser("setb"); p.add_argument("file", type=Path); p.add_argument("pairs", nargs="+")
    a = ap.parse_args()

    if a.cmd == "show":
        cmd_show(a.file, a.n)
    elif a.cmd == "set":
        cmd_set(a.file, a.pairs)
    elif a.cmd == "stat":
        cmd_stat(a.file)
    elif a.cmd == "showb":
        cmd_showb(a.file, a.results, a.n)
    elif a.cmd == "setb":
        cmd_setb(a.file, a.pairs)
    else:
        cmd_sync(a.src, a.dst)


if __name__ == "__main__":
    main()
