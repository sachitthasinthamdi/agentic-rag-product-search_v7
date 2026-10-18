r"""สร้างไฟล์ป้าย ข ของแขนใดก็ได้ — ยกป้ายจาก A3 มาเฉพาะข้อที่คำตอบเหมือนกันเป๊ะ

ป้าย ข ติดบนคำตอบของ A3 เป็นหลัก แขนอื่นที่คำตอบเหมือนกันทุกตัวอักษรจึงยกป้ายมาได้
ข้อที่คำตอบต่างกันต้องอ่านของแขนนั้นเองแล้วติดป้ายใหม่ → ปล่อยว่างไว้

รัน:  .venv\Scripts\python.exe eval\labelling\make_arm_labels.py <en3|th3|th4> <A1|A3C>
"""
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = {
    "en3": ("collection_20261013_1329.json", "labels_b3_full.csv"),
    "th3": ("collection_th_20261013_1506.json", "labels_b3_th_full.csv"),
    "th4": ("collection_th_20261013_1900.json", "labels_b4_th_full.csv"),
}


def main() -> None:
    if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    key, arm = sys.argv[1], sys.argv[2].upper()
    res_file, base_file = RUNS[key]
    raw = json.loads((ROOT / "eval/results" / res_file).read_text(encoding="utf-8"))["raw"]
    g1 = [g for g in raw["A3_r1"] if "g1" in g or "in_domain" in g][0]
    ref, own = raw["A3_r1"][g1], raw[f"{arm}_r1"][g1]
    base = {r["qid"]: r for r in
            csv.DictReader((ROOT / "eval/labels" / base_file).open(encoding="utf-8-sig", newline=""))}

    rows, blank = [], []
    for qid, r in base.items():
        pk = own[qid].get("picked") or []
        same = own[qid]["reply"] == ref[qid]["reply"]
        row = dict(r)
        row["n_products"] = len(pk)
        if same:
            row["note"] = r["note"].rstrip() + f"  [{arm} คำตอบเหมือน A3 ทุกตัวอักษร ยกป้ายมา]"
        else:
            row["label"] = row["kind"] = row["note"] = ""
            blank.append(qid)
        rows.append(row)

    out = ROOT / "eval/labels" / base_file.replace(".csv", f"_{arm.lower()}.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"เขียน {out.name} · {len(rows)} แถว · ยกป้ายมา {len(rows)-len(blank)} · "
          f"ต้องติดใหม่ {len(blank)}: {' '.join(blank)}")


if __name__ == "__main__":
    main()
