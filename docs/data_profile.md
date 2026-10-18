# รายงานสำรวจข้อมูลดิบ (ทุกแถว)

ไฟล์: `data/raw/products_raw.feather` · **117,243 แถว × 16 คอลัมน์** (รวม `embeddings` ที่ไม่ได้นำมาวิเคราะห์)

อ่านครบทุกแถว ไม่ได้สุ่มตัวอย่าง · สร้างโดย `tools/profile_raw.py`

## 1. ภาพรวมทุกคอลัมน์

| คอลัมน์ | ชนิด | ว่าง/หาย | ค่าไม่ซ้ำ | ตัวอย่าง |
|---|---|---|---|---|
| `parent_asin` | str | 0 (0.0%) | 117,243 | B000044U2O |
| `date_first_available` | datetime64[ns] | 0 (0.0%) | 363 | 2023-04-29 00:00:00 |
| `title` | str | 0 (0.0%) | 114,687 | Anomie & Bonhomie |
| `description` | str | 0 (0.0%) | 104,321 | Amazon.com Fans of Scritti Politti's synth-pop-funk masterpi |
| `filename` | str | 0 (0.0%) | 30 | meta_Digital_Music |
| `main_category` | str | 24,805 (21.2%) | 37 | Digital Music |
| `categories` | object | 2,587 (2.2%) | — | ['Musical Instruments' 'Drums & Percussion' 'Drum Sets & Set |
| `store` | str | 255 (0.2%) | 44,287 | Scritti Politti   Format: Audio CD |
| `average_rating` | float64 | 0 (0.0%) | 41 | 4.2 |
| `rating_number` | float64 | 6 (0.0%) | 2,534 | 56.0 |
| `price` | float64 | 35,869 (30.6%) | 8,726 | 19.98 |
| `features` | object | 5,820 (5.0%) | — | ['Release Date - 27th January 2023'  'Officially distributed |
| `details` | str | 0 (0.0%) | 108,703 | {'Date First Available': 'April 29, 2023'} |
| `image` | str | 0 (0.0%) | 114,168 | https://m.media-amazon.com/images/I/41T618NE88L.jpg |
| `__index_level_0__` | int64 | 0 (0.0%) | 117,243 | 1 |

## 2. ความยาวของข้อความ (จำนวนตัวอักษร)

| คอลัมน์ | สั้นสุด | p25 | มัธยฐาน | p75 | ยาวสุด | ว่าง | สั้นกว่า 20 ตัวอักษร |
|---|---|---|---|---|---|---|---|
| `title` | 1 | 72 | 120 | 171 | 499 | 0 | 1,702 |
| `description` | 1 | 208 | 520 | 1,018 | 17,217 | 0 | 3,305 |
| `details` | 39 | 131 | 270 | 493 | 9,077 | 0 | 0 |
| `store` | 0 | 6 | 7 | 10 | 586 | 255 | 112,823 |
| `image` | 51 | 63 | 63 | 63 | 151 | 0 | 0 |

- `features` (ลิสต์ข้อความ): ว่าง 5,820 แถว (5.0%) · มัธยฐาน 5 ข้อ · มากสุด 22 ข้อ

## 3. คอลัมน์ `details` (ข้อมูลจำเพาะสินค้า)

- แปลงเป็น dict ไม่สำเร็จ: **0 แถว** (0.0%)
- จำนวน key ต่อสินค้า: มัธยฐาน 7 · เฉลี่ย 9.2 · มากสุด 54 · ไม่มี key เลย 0 แถว
- ชนิดของ key ที่พบทั้งหมด: **3,308 ชนิด** (schema-less — แต่ละสินค้ามี key ไม่เหมือนกัน)

**key ที่พบบ่อยที่สุด 25 อันดับ** (สัดส่วนของสินค้าทั้งหมดที่มี key นี้)

| key | มีกี่แถว | สัดส่วน |
|---|---|---|
| Date First Available | 117,101 | 99.9% |
| Manufacturer | 91,345 | 77.9% |
| Item model number | 58,118 | 49.6% |
| Brand | 54,297 | 46.3% |
| Best Sellers Rank | 51,963 | 44.3% |
| Item Weight | 50,746 | 43.3% |
| Department | 46,055 | 39.3% |
| Product Dimensions | 41,628 | 35.5% |
| Color | 40,936 | 34.9% |
| Material | 30,827 | 26.3% |
| Package Dimensions | 29,830 | 25.4% |
| Country of Origin | 23,846 | 20.3% |
| Special Feature | 20,485 | 17.5% |
| Style | 17,108 | 14.6% |
| Included Components | 13,283 | 11.3% |
| Size | 12,659 | 10.8% |
| Shape | 12,199 | 10.4% |
| Number of Items | 11,688 | 10.0% |
| Age Range (Description) | 9,456 | 8.1% |
| Theme | 8,584 | 7.3% |
| Manufacturer Part Number | 8,572 | 7.3% |
| Pattern | 8,423 | 7.2% |
| Product Care Instructions | 7,990 | 6.8% |
| Unit Count | 7,812 | 6.7% |
| Number of Pieces | 7,057 | 6.0% |

## 4. หมวดหมู่สินค้า

- `main_category`: หาย **24,805 แถว** (21.2%) · มี 37 ค่า
- `categories` (ลิสต์): ว่าง 2,587 แถว (2.2%)
- `filename`: หาย 0 แถว · มี 30 ค่า

**ถ้าเอา `categories[0]` มาเติมตอน `main_category` หาย** จะกู้ได้ 24,264 แถว เหลือหาย 541 แถว (0.5%)

**ค่าของ `filename` ทั้งหมด** (ใช้เป็นตาข่ายรองสุดท้ายได้ไหม)

- `meta_Clothing_Shoes_and_Jewelry` — 41,777 แถว
- `meta_Home_and_Kitchen` — 17,326 แถว
- `meta_Electronics` — 7,681 แถว
- `meta_Automotive` — 7,161 แถว
- `meta_Sports_and_Outdoors` — 6,343 แถว
- `meta_Cell_Phones_and_Accessories` — 5,062 แถว
- `meta_Tools_and_Home_Improvement` — 4,776 แถว
- `meta_Health_and_Household` — 4,760 แถว
- `meta_Office_Products` — 3,545 แถว
- `meta_Patio_Lawn_and_Garden` — 3,075 แถว
- `meta_Arts_Crafts_and_Sewing` — 2,948 แถว
- `meta_Pet_Supplies` — 2,742 แถว
- `meta_Beauty_and_Personal_Care` — 1,402 แถว
- `meta_Toys_and_Games` — 1,367 แถว
- `meta_CDs_and_Vinyl` — 1,319 แถว
- `meta_Industrial_and_Scientific` — 1,216 แถว
- `meta_Handmade_Products` — 1,018 แถว
- `meta_Musical_Instruments` — 639 แถว
- `meta_Appliances` — 573 แถว
- `meta_Video_Games` — 561 แถว
- `meta_Unknown` — 541 แถว
- `meta_Baby_Products` — 526 แถว
- `meta_Amazon_Fashion` — 470 แถว
- `meta_Software` — 157 แถว
- `meta_Grocery_and_Gourmet_Food` — 96 แถว
- `meta_Health_and_Personal_Care` — 93 แถว
- `meta_Digital_Music` — 56 แถว
- `meta_Gift_Cards` — 8 แถว
- `meta_Magazine_Subscriptions` — 3 แถว
- `meta_Books` — 2 แถว

**หมวดจาก `main_category` 15 อันดับแรก**

| หมวด | จำนวน | สัดส่วน |
|---|---|---|
| AMAZON FASHION | 36,460 | 31.1% |
| Amazon Home | 13,874 | 11.8% |
| Tools & Home Improvement | 7,945 | 6.8% |
| Automotive | 5,980 | 5.1% |
| Cell Phones & Accessories | 3,471 | 3.0% |
| Health & Personal Care | 3,416 | 2.9% |
| All Electronics | 3,136 | 2.7% |
| Sports & Outdoors | 2,942 | 2.5% |
| Office Products | 2,925 | 2.5% |
| Industrial & Scientific | 2,460 | 2.1% |
| Pet Supplies | 1,907 | 1.6% |
| Computers | 1,724 | 1.5% |
| Digital Music | 1,379 | 1.2% |
| Handmade | 1,127 | 1.0% |
| Arts, Crafts & Sewing | 874 | 0.7% |

## 5. ตัวเลข

| คอลัมน์ | หาย | ต่ำสุด | p25 | มัธยฐาน | p75 | p99 | สูงสุด |
|---|---|---|---|---|---|---|---|
| `price` | 35,869 (30.6%) | 0.00 | 12.99 | 20.29 | 39.99 | 623.78 | 49,484.08 |
| `average_rating` | 0 (0.0%) | 1.00 | 3.80 | 4.40 | 4.70 | 5.00 | 5.00 |
| `rating_number` | 6 (0.0%) | 1.00 | 3.00 | 10.00 | 30.00 | 1,898.64 | 258,497.00 |

- ราคา ≤ 0 (เป็นไปไม่ได้จริง): **110 แถว**
- ราคา > $1,000: 360 แถว (0.3%) · สูงสุด $49,484.08
- คะแนนนอกช่วง 1-5: 0 แถว
- สินค้าที่มีรีวิวเพียง 1 ครั้ง: 17,171 แถว (14.6%)

## 6. ความซ้ำ

- `parent_asin` ซ้ำ: **0 แถว** (ใช้เป็นรหัสประจำสินค้าได้)
- `title` ซ้ำเป๊ะ: 2,556 แถว (2.2%)
- `title` ซ้ำเมื่อไม่สนตัวพิมพ์เล็กใหญ่: 2,605 แถว (2.2%)

## 7. ภาษาและความสะอาดของข้อความ

- ชื่อสินค้าที่มีอักษรไทย: **0 แถว** (0.0%)
- ชื่อสินค้าที่มีอักษรจีน/ญี่ปุ่น/เกาหลี: 229 แถว (0.2%)
- ชื่อสินค้าที่มีอักขระนอก ASCII (รวมสัญลักษณ์ อีโมจิ ตัวหนอน): 6,019 แถว (5.1%)
- คำอธิบายที่มีแท็ก HTML ปนมา: 23 แถว (0.0%)