import io, json, re, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[2]   # รากโปรเจกต์ หาเองจากตำแหน่งไฟล์
ROOT = _P(__file__).resolve().parents[2] / "eval" / "results"
def reasons(reply):
    out, blk = [], []
    for ln in reply.split("\n"):
        if re.match(r"^\d+\.\s", ln):
            if len(blk) >= 3: out.append(blk[2].strip())
            blk = [ln]
        else: blk.append(ln)
    if len(blk) >= 3: out.append(blk[2].strip())
    return out
ARMS = ("A1_r1", "A3C_r1", "A3_r1")
for tag, f in (("รอบ 3", "collection_th_20261013_1506.json"),
               ("รอบ 4", "collection_th_20261013_1900.json")):
    raw = json.loads((ROOT / f).read_text(encoding="utf-8"))["raw"]
    band = [0, 0, 0, 0]; ex = [[], [], [], []]
    for a in ARMS:
        for g in raw[a]:
            for qid, r in raw[a][g].items():
                if not (r.get("picked") or []) or r.get("weak"): continue
                for x in reasons(r["reply"]):
                    if not x.strip(): continue
                    th = len(re.findall(r"[\u0e00-\u0e7f]", x)); en = len(re.findall(r"[A-Za-z]", x))
                    fr = th / (th + en) if th + en else 0
                    k = 0 if fr < 0.05 else 1 if fr < 0.4 else 2 if fr < 0.7 else 3
                    band[k] += 1
                    if len(ex[k]) < 3: ex[k].append(x)
    n = sum(band)
    name = ["อังกฤษล้วน (พังจริง)", "อังกฤษเป็นหลัก", "ไทยปนชื่อแบรนด์เยอะ", "ไทยเป็นหลัก"]
    print(f"=== {tag} · {n} บรรทัดที่มีเนื้อหา ===")
    for k in range(4):
        print(f"  {name[k]:22} {band[k]:>3} ({band[k]/n*100:4.1f}%)")
    print("  ตัวอย่างกลุ่ม 'อังกฤษล้วน':")
    for x in ex[0]: print("     ", x[:92])
    print("  ตัวอย่างกลุ่ม 'ไทยปนชื่อแบรนด์เยอะ':")
    for x in ex[2]: print("     ", x[:92])
    print()
