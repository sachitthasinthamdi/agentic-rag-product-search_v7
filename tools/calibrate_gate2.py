r"""หาค่าประตูชั้นสอง — ของที่ลูปหามาในรอบค้นซ้ำ ต้องมั่นใจแค่ไหนถึงจะตอบ

**ปัญหาที่แก้** ตอนนี้ของจากทุกรอบใช้ประตูเดียวกัน (`GATE = 0.55`) ทำให้ลูป
ตอบคำค้นที่คลังไม่มีของ 4 ข้อในชุดทดสอบ · ประตูชั้นสองคือ "ของที่มาจาก
รอบ >= 2 ต้องมีอย่างน้อย 1 ชิ้นที่คะแนนถึงเกณฑ์นี้ ถึงจะตอบ"

**ทำไมใช้กองของ gate1 ไม่ได้** คำขอบริการใน `OOD_QUERIES` นอกคลังเกินไป —
ลูปยิง 2-3 รอบจริงแต่หาของเหนือ 0.55 ไม่ได้เลย **จึงไม่มีคะแนนให้หาเส้นแบ่ง**
(docs/steps.md ข้อ 356-359)

**กองนี้ออกแบบให้ลูปยิงทุกคำ** ตรวจแล้วว่าทุกคำผ่านประตูรอบแรกได้ < 3 ชิ้น

| ฝั่ง | จำนวน | เฉลยรู้ล่วงหน้าเพราะ |
|---|---|---|
| ควรตก | 24 | ชื่อคนดัง + หมวดที่คลังไม่มีเลย — คลังขายแต่สินค้า **อะไรที่ลูปหามาได้ผิดหมด** |
| ควรผ่าน | 12 | คำสะกดผิดของสินค้าที่**ยืนยันด้วยโค้ดแล้ว**ว่าคลังมี (คำถูกผ่าน >= 3) |

⚠ ข้อจำกัด: ฝั่งควรผ่านเป็นคำสะกดผิดที่ผู้วิจัยแต่งเอง ไม่ได้มาจากผู้ใช้จริง
(แต่ `loui vuitton` · `white rear fiew mirror` ใน ESCI ยืนยันว่าคนสะกดผิดจริง)

รัน:  python tools\calibrate_gate2.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.a3c import A3C                                          # noqa: E402

# ---------------------------------------------------------------------------
# ควรตก — ลูปหาอะไรมาได้ก็ผิด เพราะคลังไม่มีสิ่งนี้
# ---------------------------------------------------------------------------
SHOULD_FAIL = [
    "rory mcilroy", "haruki murakami", "yo yo ma cellist", "simone biles",
    "ansel adams", "zadie smith", "lang lang pianist", "katie ledecky",
    "wassily kandinsky", "joan didion", "novak djokovic", "yayoi kusama",
    "kazuo ishiguro", "renzo piano architect", "martha argerich",
    "eliud kipchoge", "chimamanda adichie", "glenn gould", "sofia coppola",
    "thelonious monk",
    "steinway grand piano", "cessna 172 aircraft",
    "hyperbaric oxygen chamber", "mri scanner machine",
]

# ---------------------------------------------------------------------------
# ควรผ่าน — (คำสะกดผิด, คำถูก) · ตรวจแล้วว่าคำถูกผ่านประตู >= 3 ชิ้น
# ---------------------------------------------------------------------------
SHOULD_PASS = [
    ("blutooth speker", "bluetooth speaker"),
    ("memry foem pilow", "memory foam pillow"),
    ("yoge matt", "yoga mat"),
    ("laptp stnad", "laptop stand"),
    ("cast iorn skilet", "cast iron skillet"),
    ("blakout curtins", "blackout curtains"),
    ("phon cace shokproof", "phone case shockproof"),
    ("gardin hos nozel", "garden hose nozzle"),
    ("dawg chue toi", "dog chew toy"),
    ("pait rollar", "paint roller"),
    ("carr fone mownt", "car phone mount"),
    ("dsk orgnizer", "desk organizer"),
]


def top_score(turn) -> float | None:
    """คะแนนสูงสุดของชิ้นที่ระบบเลือกจะตอบ · None = ปฏิเสธ"""
    return max((h.score for h in turn.hits), default=None)


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    fail_scores, pass_scores = [], []

    with A3C() as arm:
        print(f"ควรตก {len(SHOULD_FAIL)} คำ · ควรผ่าน {len(SHOULD_PASS)} คำ\n")
        print(f"   {'คำค้น':<32}{'รอบ':>5}{'ตอบ':>5}{'คะแนนสูงสุด':>13}")
        print("   " + "-" * 56)
        for q in SHOULD_FAIL:
            arm.reset()
            t = arm.respond(q)
            s = top_score(t)
            if s is not None:
                fail_scores.append((s, q))
            print(f"   {q[:30]:<32}{t.trace['n_searches']:>5}{len(t.hits):>5}"
                  f"{(f'{s:.3f}' if s else 'ปฏิเสธ'):>13}")
        print()
        for bad, good in SHOULD_PASS:
            arm.reset()
            t = arm.respond(bad)
            s = top_score(t)
            if s is not None:
                pass_scores.append((s, bad))
            print(f"   {bad[:30]:<32}{t.trace['n_searches']:>5}{len(t.hits):>5}"
                  f"{(f'{s:.3f}' if s else 'ปฏิเสธ'):>13}   -> {good}")

    print("\n" + "=" * 70)
    print(f"ควรตก  · ตอบมา {len(fail_scores)}/{len(SHOULD_FAIL)} คำ"
          + (f" · คะแนนสูงสุด {max(s for s, _ in fail_scores):.3f}" if fail_scores else ""))
    print(f"ควรผ่าน · ตอบมา {len(pass_scores)}/{len(SHOULD_PASS)} คำ"
          + (f" · คะแนนต่ำสุด {min(s for s, _ in pass_scores):.3f}" if pass_scores else ""))
    if fail_scores and pass_scores:
        hi = max(s for s, _ in fail_scores)
        lo = min(s for s, _ in pass_scores)
        if hi < lo:
            print(f"\n✅ แยกขาด · ช่องว่าง {hi:.3f} - {lo:.3f}"
                  f" · **กลางช่องว่าง = {(hi + lo) / 2:.3f}**")
        else:
            print(f"\n❌ เหลื่อมกัน · ควรตกสูงสุด {hi:.3f} >= ควรผ่านต่ำสุด {lo:.3f}"
                  f" → ประตูชั้นสองแยกสองฝั่งนี้ไม่ได้")
        for th in (0.56, 0.57, 0.58, 0.59):
            keep = sum(1 for s, _ in pass_scores if s >= th)
            leak = sum(1 for s, _ in fail_scores if s >= th)
            print(f"   ถ้าตั้งที่ {th:.2f}: เก็บของดี {keep}/{len(pass_scores)}"
                  f" · ยังปล่อยของผิด {leak}/{len(fail_scores)}")
    elif not fail_scores:
        print("\n⚠ ฝั่งควรตกปฏิเสธหมดทุกคำ — ไม่มีคะแนนให้หาเส้นแบ่ง"
              " แปลว่าประตูเดิม 0.55 เพียงพออยู่แล้วสำหรับกองนี้")


if __name__ == "__main__":
    main()
