"""ขั้นที่ 4.2-4.3 — แปลง embed_text เป็นเวกเตอร์ แล้วเก็บเป็นไฟล์

**ทำไมเก็บเป็นไฟล์ `.npy` ไม่ยัดเข้าฐานข้อมูลตรง ๆ:** การแปลงใช้เวลา ~37 นาที
ถ้าเก็บไว้ในฐานข้อมูลอย่างเดียว พอฐานพัง/อยากเปลี่ยนฐาน/อยากลองสถาปัตยกรรมใหม่
ก็ต้องแปลงใหม่ทุกครั้ง · แยกเก็บเป็นไฟล์แล้วสร้างฐานใหม่ใช้เวลาไม่กี่นาที

ไฟล์ที่ได้ 3 ตัว:
    bge-m3_v1.npy          เวกเตอร์ (float16) — ตัวที่ต้องหวงไว้
    bge-m3_v1.ids.feather  parent_asin เรียงตรงกับแถวใน .npy
    bge-m3_v1.meta.json    ชื่อโมเดล · มิติ · sha256 ของ embed_text ทั้งคอลัมน์

`sha256` ใน meta ใช้ **ตรวจอัตโนมัติว่าเวกเตอร์ตรงกับข้อความปัจจุบันหรือล้าสมัยแล้ว**
ถ้าแก้ `embed_text` แล้วลืมแปลงใหม่ จะรู้ตอนตรวจ ไม่ใช่รู้ตอนผลค้นเพี้ยน

**ทำงานต่อจากจุดที่ค้างได้** — ถ้าถูกขัดจังหวะกลางทาง รันซ้ำแล้วมันจะเริ่มจากแถวที่ยังไม่ได้ทำ

⚠ ต้องสตาร์ต Ollama ก่อน:  ollama.exe serve

รัน:  python src\\embed.py [--limit N] [--batch 32]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FEATURE_FILE = ROOT / "data" / "feature" / "products_feature.feather"
VECTOR_DIR = ROOT / "data" / "vectors"

MODEL = "bge-m3"
VERSION = "v1"                 # เลขเวอร์ชันของ embed_text — แก้ข้อความแล้วต้องขึ้น v2
TAG = f"{MODEL}_{VERSION}"
DIM = 1024                     # BGE-M3 คืนเวกเตอร์ 1,024 มิติ
DTYPE = np.float16             # ครึ่งขนาดของ float32 และไม่กระทบอันดับผลค้น

OLLAMA_URL = "http://localhost:11434"
CHECKPOINT_EVERY = 5_000       # เซฟความคืบหน้าทุกเท่านี้แถว เผื่อถูกขัดจังหวะ


def paths() -> tuple[Path, Path, Path, Path]:
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    return (VECTOR_DIR / f"{TAG}.npy",
            VECTOR_DIR / f"{TAG}.ids.feather",
            VECTOR_DIR / f"{TAG}.meta.json",
            VECTOR_DIR / f"{TAG}.partial.npy")


def text_fingerprint(texts: pd.Series) -> str:
    """ลายนิ้วมือของ embed_text ทั้งคอลัมน์ — ใช้ตรวจว่าเวกเตอร์ล้าสมัยหรือยัง"""
    h = hashlib.sha256()
    for text in texts:
        h.update(text.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def health_check() -> None:
    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SystemExit(
            f"❌ ต่อ Ollama ที่ {OLLAMA_URL} ไม่ได้ — สตาร์ตก่อนด้วย `ollama.exe serve`\n   {exc}"
        ) from exc
    names = {m["name"].split(":")[0] for m in response.json().get("models", [])}
    if MODEL not in names:
        raise SystemExit(f"❌ ไม่พบโมเดล '{MODEL}' บน Ollama (มี: {sorted(names)})\n"
                         f"   ดึงก่อนด้วย `ollama pull {MODEL}`")


def embed_batch(client: httpx.Client, texts: list[str], max_retries: int = 4) -> np.ndarray:
    """เข้ารหัสข้อความชุดหนึ่ง — ลองใหม่แบบถอยหลังทวีคูณถ้า Ollama สะดุด"""
    for attempt in range(1, max_retries + 1):
        try:
            response = client.post(f"{OLLAMA_URL}/api/embed",
                                   json={"model": MODEL, "input": texts})
            response.raise_for_status()
            vectors = response.json().get("embeddings")
            if not vectors or len(vectors) != len(texts):
                raise ValueError(f"ขอ {len(texts)} เวกเตอร์ แต่ได้ {len(vectors or [])}")
            return np.asarray(vectors, dtype=DTYPE)
        except (httpx.HTTPError, ValueError) as exc:
            if attempt == max_retries:
                raise SystemExit(f"❌ แปลงไม่สำเร็จหลังลอง {max_retries} ครั้ง: {exc}") from exc
            wait = 2 ** attempt
            print(f"   สะดุด ({type(exc).__name__}) รอ {wait} วินาทีแล้วลองใหม่ "
                  f"({attempt}/{max_retries})")
            time.sleep(wait)
    raise AssertionError("ไม่ควรมาถึงบรรทัดนี้")


def run(limit: int | None = None, batch_size: int = 32) -> None:
    npy_file, ids_file, meta_file, partial_file = paths()

    print("อ่านชั้น feature ...")
    df = pd.read_feather(FEATURE_FILE, columns=["parent_asin", "embed_text"])
    if limit:
        df = df.head(limit)
    n = len(df)
    texts = df["embed_text"].tolist()
    print(f"  {n:,} แถว · ความยาวเฉลี่ย {df['embed_text'].str.len().mean():,.0f} ตัวอักษร")

    health_check()

    # --- ทำต่อจากจุดที่ค้าง ---
    vectors = np.zeros((n, DIM), dtype=DTYPE)
    done = 0
    if partial_file.exists():
        saved = np.load(partial_file)
        if saved.shape[1] == DIM and saved.shape[0] <= n:
            done = int(saved.shape[0])
            vectors[:done] = saved
            print(f"  พบงานค้างไว้ {done:,} แถว — ทำต่อจากแถวที่ {done + 1:,}")
        else:
            print("  ไฟล์งานค้างไม่เข้ากับข้อมูลปัจจุบัน — เริ่มใหม่")

    if done >= n:
        print("  แปลงครบแล้ว ข้ามไปเขียนไฟล์ผลลัพธ์")
    else:
        print(f"\nเริ่มแปลง (ประมาณ {(n - done) * 0.027 / 60:.0f} นาที) ...")
        started = time.perf_counter()
        with httpx.Client(timeout=600) as client:
            for start in range(done, n, batch_size):
                chunk = texts[start:start + batch_size]
                vectors[start:start + len(chunk)] = embed_batch(client, chunk)
                finished = start + len(chunk)

                if finished % CHECKPOINT_EVERY < batch_size or finished == n:
                    np.save(partial_file, vectors[:finished])
                    elapsed = time.perf_counter() - started
                    per_doc = elapsed / (finished - done)
                    print(f"   {finished:,}/{n:,} ({finished/n*100:.1f}%) · "
                          f"{per_doc*1000:.1f} ms/ชิ้น · "
                          f"เหลือประมาณ {(n - finished) * per_doc / 60:.0f} นาที")
        print(f"แปลงเสร็จใน {(time.perf_counter() - started) / 60:.1f} นาที")

    # --- ตรวจความถูกต้องก่อนเขียนไฟล์จริง ---
    print("\nตรวจคุณภาพ ...")
    norms = np.linalg.norm(vectors.astype(np.float32), axis=1)
    zero_rows = int((norms < 1e-6).sum())
    if zero_rows:
        raise SystemExit(f"❌ มีเวกเตอร์ว่าง {zero_rows:,} แถว — การแปลงไม่สมบูรณ์")
    print(f"  ไม่มีเวกเตอร์ว่าง · ความยาวเวกเตอร์ (norm) เฉลี่ย {norms.mean():.4f} "
          f"(BGE-M3 normalize มาแล้ว ควรใกล้ 1.0)")

    np.save(npy_file, vectors)
    df[["parent_asin"]].reset_index(drop=True).to_feather(ids_file)
    meta = {
        "tag": TAG,
        "model": MODEL,
        "model_source": "ollama",
        "version": VERSION,
        "dim": DIM,
        "dtype": str(np.dtype(DTYPE)),
        "rows": n,
        "granularity": "1 product = 1 vector",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embed_text_sha256": text_fingerprint(df["embed_text"]),
        "source_file": str(FEATURE_FILE.relative_to(ROOT)),
        "note": ("เวกเตอร์ normalize แล้ว (cosine = dot product) · "
                 "sha256 ใช้ตรวจว่าตรงกับ embed_text ปัจจุบันหรือล้าสมัย"),
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    partial_file.unlink(missing_ok=True)

    print(f"\nเขียนไฟล์:")
    for path in (npy_file, ids_file, meta_file):
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1_048_576:,.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="แปลง embed_text เป็นเวกเตอร์เก็บเป็นไฟล์")
    parser.add_argument("--limit", type=int, help="จำกัดจำนวนแถว (สำหรับทดสอบ)")
    parser.add_argument("--batch", type=int, default=32, help="ขนาด batch ที่ส่งให้ Ollama")
    args = parser.parse_args()
    run(args.limit, args.batch)


if __name__ == "__main__":
    main()
