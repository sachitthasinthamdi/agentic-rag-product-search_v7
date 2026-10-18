"""ชุดทดสอบที่ล็อกแล้ว — ห้ามแก้หลังรันครั้งแรก

ที่มาของคำค้น: **ยืมข้อความคำค้นจริงจากภายนอก ไม่ได้ยืมป้าย**
  ESCI  (Reddy et al. 2022)  — คำค้นจริงของผู้ใช้ Amazon
  WANDS (Chen et al. 2022)   — คำค้นจริงของผู้ใช้ Wayfair

ทำไมไม่เขียนเอง: ทดลองเขียนเอง 2 รอบ (76 คำ) ได้คำค้นชั้นยาก **0 คำ** ทั้งสองรอบ
เพราะผู้เขียนไม่รู้รหัสอะไหล่จริง ศัพท์เฉพาะทาง และคำสะกดผิดที่ผู้ใช้จริงพิมพ์

ทำไมไม่ยืมป้าย: ตรวจแล้วคลัง ESCI ซ้อนทับคลังเรา 17/856,238 ด้วยรหัส
และ 148/856,238 ด้วยชื่อสินค้า -> ป้ายของเขาใช้กับคลังเราไม่ได้

วิธีคัด: ยิงคำค้นจริง 1,980 คำเข้าคลังเรา แล้ว**ให้คะแนนเป็นคนคัด**
  GROUP1  คะแนนอันดับ 1 >= 0.50 และผ่านประตู >= 3  -> คลังมีของ
  GROUP3  คะแนนอันดับ 1 < 0.47                      -> คลังไม่มีของ

⚠ ตัดคำค้น 3 คำที่เนื้อหาไม่เหมาะกับงานวิชาการออก แล้วสุ่มคำในชั้นเดียวกันมาแทน
  (กรองด้วยรายการคำสำคัญ ไม่ใช่ข้อความตรงตัว — รอบแรกกรองด้วยข้อความตรงตัว
   ทำให้คำที่ต่างกันนิดเดียวรอดมาได้)
  (เป็นการคัดด้วยเหตุผลที่ไม่เกี่ยวกับประสิทธิภาพของระบบ จึงไม่กระทบความเป็นกลาง
   แต่ต้องบันทึกไว้)

⚠ **ภาษา: รอบนี้รันภาษาอังกฤษอย่างเดียว** ภาษาไทยทำรอบถัดไป
  ป้ายผูกกับคู่ (คำค้น, สินค้า) ไม่ขึ้นกับภาษา -> ป้ายรอบนี้ใช้กับรอบไทยได้เลย
  ⚠ ESCI/WANDS **ไม่มีคำค้นภาษาไทย** -> รอบไทยต้องแปลเอง และความยากที่มาจาก
     การสะกดผิดจะหายไปตอนแปล ต้องเขียนเป็นข้อจำกัด
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# กลุ่ม 1 — คลังเรามีของ · **ต้องติดป้าย**
#   band = ชั้นความยากจากคะแนนอันดับ 1 (ง่าย >=0.68 · กลาง 0.60-0.68 · ยาก <0.60)
#   top1 = คะแนนตอนคัดกรอง เก็บไว้เพื่อให้ตรวจย้อนได้ ไม่ใช่ตัวชี้วัด
# ---------------------------------------------------------------------------

GROUP1_IN_DOMAIN = [
    {"id": "q01", "q": "usb flash drive 2 tb", "band": "ง่าย", "src": "ESCI", "top1": 0.762},
    {"id": "q02", "q": "squeaky balls for large dogs", "band": "ง่าย", "src": "ESCI", "top1": 0.746},
    {"id": "q03", "q": "gowdy height adjustable standing desk", "band": "ง่าย", "src": "WANDS", "top1": 0.733},
    {"id": "q04", "q": "tv stand with storage space", "band": "ง่าย", "src": "ESCI", "top1": 0.724},
    {"id": "q05", "q": "baby proofing cabinet lock bows", "band": "ง่าย", "src": "ESCI", "top1": 0.709},
    {"id": "q06", "q": "led light strip", "band": "ง่าย", "src": "WANDS", "top1": 0.709},
    {"id": "q07", "q": "scat mats for dogs", "band": "ง่าย", "src": "ESCI", "top1": 0.706},
    {"id": "q08", "q": "toilet paper stand", "band": "ง่าย", "src": "WANDS", "top1": 0.701},
    {"id": "q09", "q": "5 blade electric razors for men", "band": "ง่าย", "src": "ESCI", "top1": 0.698},
    {"id": "q10", "q": "chair pillow cushion", "band": "ง่าย", "src": "WANDS", "top1": 0.692},
    {"id": "q11", "q": "lunch bag", "band": "ง่าย", "src": "WANDS", "top1": 0.692},
    {"id": "q12", "q": "adidas dad hat", "band": "ง่าย", "src": "ESCI", "top1": 0.688},
    {"id": "q13", "q": "iphone 10 xr otterbox case for women", "band": "ง่าย", "src": "ESCI", "top1": 0.686},
    {"id": "q14", "q": "expo wipes for white board", "band": "ง่าย", "src": "ESCI", "top1": 0.686},
    {"id": "q15", "q": "decorative vinyl window decal", "band": "ง่าย", "src": "ESCI", "top1": 0.684},
    {"id": "q16", "q": "masquerade mask for women", "band": "ง่าย", "src": "ESCI", "top1": 0.684},
    {"id": "q17", "q": "gaming chair with footrest and speakers", "band": "ง่าย", "src": "ESCI", "top1": 0.683},
    {"id": "q18", "q": "pool floats", "band": "ง่าย", "src": "WANDS", "top1": 0.681},
    {"id": "q19", "q": "accent leather chair", "band": "กลาง", "src": "WANDS", "top1": 0.670},
    {"id": "q20", "q": "reflective cat harness", "band": "กลาง", "src": "ESCI", "top1": 0.668},
    {"id": "q21", "q": "ps4 controller charger", "band": "กลาง", "src": "ESCI", "top1": 0.665},
    {"id": "q22", "q": "battery terminals toyota", "band": "กลาง", "src": "ESCI", "top1": 0.656},
    {"id": "q23", "q": "11 ipad pro case", "band": "กลาง", "src": "ESCI", "top1": 0.654},
    {"id": "q24", "q": "1 1/2 pop up drain without overflow", "band": "กลาง", "src": "ESCI", "top1": 0.650},
    {"id": "q25", "q": "grounding shoes", "band": "กลาง", "src": "ESCI", "top1": 0.644},
    {"id": "q26", "q": "lumi baby monitor with camera and audio", "band": "กลาง", "src": "ESCI", "top1": 0.640},
    {"id": "q27", "q": "portable cologne sprayer", "band": "กลาง", "src": "ESCI", "top1": 0.639},
    {"id": "q28", "q": "# 2 pencils not sharpened", "band": "กลาง", "src": "ESCI", "top1": 0.632},
    {"id": "q29", "q": "dji new drone", "band": "กลาง", "src": "ESCI", "top1": 0.629},
    {"id": "q30", "q": "ecloth glass and polishing cloth", "band": "กลาง", "src": "ESCI", "top1": 0.626},
    {"id": "q31", "q": "inspirational tags", "band": "กลาง", "src": "ESCI", "top1": 0.626},
    {"id": "q32", "q": "garmin dash cam mini", "band": "กลาง", "src": "ESCI", "top1": 0.616},
    {"id": "q33", "q": "front porch furniture sets", "band": "กลาง", "src": "WANDS", "top1": 0.610},
    {"id": "q34", "q": "orange track pants men", "band": "กลาง", "src": "ESCI", "top1": 0.605},
    {"id": "q35", "q": "decorative hour glass gold", "band": "กลาง", "src": "ESCI", "top1": 0.605},
    {"id": "q36", "q": "iron beads ideas design", "band": "กลาง", "src": "ESCI", "top1": 0.601},
    {"id": "q37", "q": "bed risers", "band": "ยาก", "src": "WANDS", "top1": 0.599},
    {"id": "q38", "q": "circle cabinet pulls", "band": "ยาก", "src": "WANDS", "top1": 0.593},
    {"id": "q39", "q": "aline skirt", "band": "ยาก", "src": "ESCI", "top1": 0.592},
    {"id": "q40", "q": "gecko repellent", "band": "ยาก", "src": "ESCI", "top1": 0.588},
    {"id": "q41", "q": "builder gel in a bottle", "band": "ยาก", "src": "ESCI", "top1": 0.586},
    {"id": "q42", "q": "dremel attachments for dog nails", "band": "ยาก", "src": "ESCI", "top1": 0.585},
    {"id": "q43", "q": "white rear fiew mirror", "band": "ยาก", "src": "ESCI", "top1": 0.583},
    {"id": "q44", "q": "9 ft baby gate with door", "band": "ยาก", "src": "ESCI", "top1": 0.581},
    {"id": "q45", "q": "'moment case' for iphone 7 not the plus", "band": "ยาก", "src": "ESCI", "top1": 0.580},
    {"id": "q46", "q": "iq fun pack game", "band": "ยาก", "src": "ESCI", "top1": 0.577},
    {"id": "q47", "q": "balt desk", "band": "ยาก", "src": "ESCI", "top1": 0.573},
    {"id": "q48", "q": "netflix tv show stickers", "band": "ยาก", "src": "ESCI", "top1": 0.572},
    {"id": "q49", "q": "play station3", "band": "ยาก", "src": "ESCI", "top1": 0.572},
    {"id": "q50", "q": "rose pots garden", "band": "ยาก", "src": "ESCI", "top1": 0.560},
]

# ---------------------------------------------------------------------------
# กลุ่ม 3 — คลังเราไม่มีของ · **ไม่ต้องติดป้าย** (เฉลย = ไม่ควรแนะนำอะไร)
# ---------------------------------------------------------------------------

GROUP3_OUT_OF_DOMAIN = [
    {"id": "n01", "q": "kisner", "src": "WANDS", "top1": 0.450},
    {"id": "n02", "q": "nanaville", "src": "ESCI", "top1": 0.435},
    {"id": "n03", "q": "lg v40 thinq", "src": "ESCI", "top1": 0.460},
    {"id": "n04", "q": "robert whitlow the sacrifice", "src": "ESCI", "top1": 0.385},
    {"id": "n05", "q": "pokemon blind box", "src": "ESCI", "top1": 0.458},
    {"id": "n06", "q": "start without me", "src": "ESCI", "top1": 0.461},
    {"id": "n07", "q": "is this not the carpenter", "src": "ESCI", "top1": 0.464},
    {"id": "n08", "q": "chernobyl", "src": "ESCI", "top1": 0.394},
    {"id": "n09", "q": "eddie noack", "src": "ESCI", "top1": 0.430},
    {"id": "n10", "q": "warhammer 40k grey knights", "src": "ESCI", "top1": 0.468},
    {"id": "n11", "q": "tana french the searcher", "src": "ESCI", "top1": 0.430},
    {"id": "n12", "q": "patrick custome", "src": "ESCI", "top1": 0.467},
    {"id": "n13", "q": "serta kleinmon", "src": "WANDS", "top1": 0.435},
    {"id": "n14", "q": "peacock", "src": "WANDS", "top1": 0.461},
    {"id": "n15", "q": "once rejected twice desired blue moon series book 1", "src": "ESCI", "top1": 0.442},
    {"id": "n16", "q": "sedona guide book", "src": "ESCI", "top1": 0.469},
    {"id": "n17", "q": "justin brescia", "src": "ESCI", "top1": 0.396},
    {"id": "n18", "q": "shandler", "src": "ESCI", "top1": 0.469},
    {"id": "n19", "q": "americanized rebel without a green card by sara saedi", "src": "ESCI", "top1": 0.458},
    {"id": "n20", "q": "levi ackerman figure", "src": "ESCI", "top1": 0.458},
    {"id": "n21", "q": "tucker carlson books", "src": "ESCI", "top1": 0.417},
    {"id": "n22", "q": "spiderman miles lorales motorcycle", "src": "ESCI", "top1": 0.467},
    {"id": "n23", "q": "streptocarpella", "src": "ESCI", "top1": 0.436},
    {"id": "n24", "q": "mission double vanity", "src": "WANDS", "top1": 0.467},
    {"id": "n25", "q": "lake launger", "src": "ESCI", "top1": 0.443},
    {"id": "n26", "q": "tamil movies", "src": "ESCI", "top1": 0.416},
    {"id": "n27", "q": "naveen jain", "src": "ESCI", "top1": 0.435},
    {"id": "n28", "q": "richard murano", "src": "ESCI", "top1": 0.396},
    {"id": "n29", "q": "season 1 fargo", "src": "ESCI", "top1": 0.447},
    {"id": "n30", "q": "pones", "src": "ESCI", "top1": 0.453},
    {"id": "n31", "q": "ombre rug", "src": "WANDS", "top1": 0.459},
    {"id": "n32", "q": "the gallows", "src": "ESCI", "top1": 0.464},
    {"id": "n33", "q": "hnbun", "src": "ESCI", "top1": 0.447},
    {"id": "n34", "q": "sally green", "src": "ESCI", "top1": 0.435},
    {"id": "n35", "q": "drudge report", "src": "WANDS", "top1": 0.419},
    {"id": "n36", "q": "hilary hahn beethoven", "src": "ESCI", "top1": 0.423},
    {"id": "n37", "q": "patrick rothfuss doors of stone", "src": "ESCI", "top1": 0.462},
    {"id": "n38", "q": "dostoevsky", "src": "ESCI", "top1": 0.425},
    {"id": "n39", "q": "the american story david rubenstein", "src": "ESCI", "top1": 0.450},
    {"id": "n40", "q": "parker s huntington", "src": "ESCI", "top1": 0.464},
    {"id": "n41", "q": "jade dermarillwr", "src": "ESCI", "top1": 0.420},
    {"id": "n42", "q": "love after lockup", "src": "ESCI", "top1": 0.467},
    {"id": "n43", "q": "issues and ethics in the helping professions 10th edition", "src": "ESCI", "top1": 0.438},
    {"id": "n44", "q": "argenteuil", "src": "WANDS", "top1": 0.411},
    {"id": "n45", "q": "clue jr", "src": "ESCI", "top1": 0.427},
    {"id": "n46", "q": "loui vuitton", "src": "ESCI", "top1": 0.425},
    {"id": "n47", "q": "untamed glennon doyle", "src": "ESCI", "top1": 0.444},
    {"id": "n48", "q": "ava max christmas without you", "src": "ESCI", "top1": 0.467},
    {"id": "n49", "q": "kingslover, barbara", "src": "ESCI", "top1": 0.439},
    {"id": "n50", "q": "minnestrista", "src": "WANDS", "top1": 0.442},
    {"id": "n51", "q": "d.a. young kindle books", "src": "ESCI", "top1": 0.445},
    {"id": "n52", "q": "monistat 3 day treatment", "src": "ESCI", "top1": 0.456},
    {"id": "n53", "q": "the hunchback of notre dame vhs", "src": "ESCI", "top1": 0.454},
    {"id": "n54", "q": "foods that built america", "src": "ESCI", "top1": 0.416},
    {"id": "n55", "q": "karma sutra books positions", "src": "ESCI", "top1": 0.467},
    {"id": "n56", "q": "terry slippers", "src": "ESCI", "top1": 0.445},
    {"id": "n57", "q": "rudin", "src": "ESCI", "top1": 0.440},
    {"id": "n58", "q": "gepoetry", "src": "ESCI", "top1": 0.456},
    {"id": "n59", "q": "48 laws of power", "src": "ESCI", "top1": 0.395},
    {"id": "n60", "q": "steve chappell", "src": "ESCI", "top1": 0.447},
]

# ---------------------------------------------------------------------------
# กลุ่ม 4 — เติมงบลงคำค้นของกลุ่ม 1 · **ไม่ต้องติดป้าย** (เทียบราคากับงบ)
#   งบตั้งที่เปอร์เซ็นไทล์ที่ 40 ของราคาผู้เข้าชิง 20 อันดับแรก
#   -> ตัดของออก 10-14 จาก 20 ชิ้นทุกคำ เงื่อนไขจึงมีผลจริง
# ---------------------------------------------------------------------------

GROUP4_BUDGET = [
    {"id": "b01", "q": "scat mats for dogs under $11", "base_q": "scat mats for dogs", "budget": 11.0, "n_over_20": 11},
    {"id": "b02", "q": "iphone 10 xr otterbox case for women under $25", "base_q": "iphone 10 xr otterbox case for women", "budget": 25.0, "n_over_20": 11},
    {"id": "b03", "q": "white rear fiew mirror under $8", "base_q": "white rear fiew mirror", "budget": 8.0, "n_over_20": 10},
    {"id": "b04", "q": "led light strip under $12", "base_q": "led light strip", "budget": 12.0, "n_over_20": 10},
    {"id": "b05", "q": "rose pots garden under $20", "base_q": "rose pots garden", "budget": 20.0, "n_over_20": 12},
    {"id": "b06", "q": "9 ft baby gate with door under $12", "base_q": "9 ft baby gate with door", "budget": 12.0, "n_over_20": 12},
    {"id": "b07", "q": "front porch furniture sets under $160", "base_q": "front porch furniture sets", "budget": 160.0, "n_over_20": 12},
    {"id": "b08", "q": "'moment case' for iphone 7 not the plus under $13", "base_q": "'moment case' for iphone 7 not the plus", "budget": 13.0, "n_over_20": 12},
    {"id": "b09", "q": "garmin dash cam mini under $12", "base_q": "garmin dash cam mini", "budget": 12.0, "n_over_20": 12},
    {"id": "b10", "q": "dremel attachments for dog nails under $9", "base_q": "dremel attachments for dog nails", "budget": 9.0, "n_over_20": 12},
    {"id": "b11", "q": "builder gel in a bottle under $15", "base_q": "builder gel in a bottle", "budget": 15.0, "n_over_20": 10},
    {"id": "b12", "q": "baby proofing cabinet lock bows under $6", "base_q": "baby proofing cabinet lock bows", "budget": 5.5, "n_over_20": 14},
    {"id": "b13", "q": "1 1/2 pop up drain without overflow under $13", "base_q": "1 1/2 pop up drain without overflow", "budget": 13.0, "n_over_20": 11},
    {"id": "b14", "q": "accent leather chair under $140", "base_q": "accent leather chair", "budget": 140.0, "n_over_20": 12},
    {"id": "b15", "q": "expo wipes for white board under $12", "base_q": "expo wipes for white board", "budget": 12.0, "n_over_20": 12},
    {"id": "b16", "q": "aline skirt under $17", "base_q": "aline skirt", "budget": 17.0, "n_over_20": 11},
    {"id": "b17", "q": "decorative vinyl window decal under $7", "base_q": "decorative vinyl window decal", "budget": 7.0, "n_over_20": 11},
    {"id": "b18", "q": "iron beads ideas design under $14", "base_q": "iron beads ideas design", "budget": 14.0, "n_over_20": 12},
    {"id": "b19", "q": "tv stand with storage space under $148", "base_q": "tv stand with storage space", "budget": 148.0, "n_over_20": 12},
    {"id": "b20", "q": "5 blade electric razors for men under $20", "base_q": "5 blade electric razors for men", "budget": 20.0, "n_over_20": 12},
    {"id": "b21", "q": "adidas dad hat under $20", "base_q": "adidas dad hat", "budget": 20.0, "n_over_20": 12},
    {"id": "b22", "q": "portable cologne sprayer under $12", "base_q": "portable cologne sprayer", "budget": 12.0, "n_over_20": 12},
    {"id": "b23", "q": "bed risers under $70", "base_q": "bed risers", "budget": 70.0, "n_over_20": 11},
    {"id": "b24", "q": "battery terminals toyota under $18", "base_q": "battery terminals toyota", "budget": 18.0, "n_over_20": 12},
    {"id": "b25", "q": "# 2 pencils not sharpened under $7", "base_q": "# 2 pencils not sharpened", "budget": 7.0, "n_over_20": 12},
    {"id": "b26", "q": "reflective cat harness under $10", "base_q": "reflective cat harness", "budget": 10.0, "n_over_20": 12},
    {"id": "b27", "q": "squeaky balls for large dogs under $12", "base_q": "squeaky balls for large dogs", "budget": 12.0, "n_over_20": 11},
    {"id": "b28", "q": "toilet paper stand under $13", "base_q": "toilet paper stand", "budget": 13.0, "n_over_20": 13},
    {"id": "b29", "q": "usb flash drive 2 tb under $27", "base_q": "usb flash drive 2 tb", "budget": 27.0, "n_over_20": 8},
    {"id": "b30", "q": "gowdy height adjustable standing desk under $160", "base_q": "gowdy height adjustable standing desk", "budget": 160.0, "n_over_20": 10},
]


def summary() -> dict:
    from collections import Counter
    return {"group1": len(GROUP1_IN_DOMAIN),
            "group1_bands": dict(Counter(x["band"] for x in GROUP1_IN_DOMAIN)),
            "group1_src": dict(Counter(x["src"] for x in GROUP1_IN_DOMAIN)),
            "group3": len(GROUP3_OUT_OF_DOMAIN),
            "group4": len(GROUP4_BUDGET),
            "total_runs": len(GROUP1_IN_DOMAIN) + len(GROUP3_OUT_OF_DOMAIN)
                          + len(GROUP4_BUDGET)}


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    for k, v in summary().items():
        print(f"{k:<16}{v}")
