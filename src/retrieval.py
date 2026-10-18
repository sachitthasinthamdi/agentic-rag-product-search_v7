"""ชั้นที่ 3 — Retrieval API

**หน้าตาเดียวที่ทุกสถาปัตยกรรมเรียกใช้ร่วมกัน** ไม่ว่าจะเป็น RAG ธรรมดา,
agent เดี่ยวที่วางแผนเอง, หรือหลาย agent ทำงานร่วมกัน — ทุกแบบเรียก `search()` ตัวนี้

**สิ่งที่ไฟล์นี้จงใจไม่รู้:** ใครเรียก · เรียกกี่รอบ · ใครตัดสินว่าจะค้นอะไร ·
จะเอาผลไปทำอะไรต่อ — ตรรกะเหล่านั้นอยู่ชั้นบน (สถาปัตยกรรม) ทั้งหมด

ที่แยกแบบนี้เพราะวิทยานิพนธ์ต้องเทียบหลายสถาปัตยกรรม ถ้าชั้นนี้ผูกกับสถาปัตยกรรมใดแบบหนึ่ง
การเทียบจะไม่แฟร์ (เพราะคนละชั้นค้นหาไม่เหมือนกัน) และต้องสร้างดัชนีใหม่ทุกครั้งที่เปลี่ยนแบบ

⚠ ต้องสตาร์ต Ollama ก่อน:  ollama.exe serve
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import chromadb
import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed import DIM, MODEL, OLLAMA_URL, TAG   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION = f"products_{TAG}"


@dataclass
class Hit:
    """ผลการค้นหนึ่งรายการ"""
    id: str                               # parent_asin
    score: float                          # ความใกล้เคียง 0-1 (ยิ่งมากยิ่งใกล้)
    title: str
    category: str
    price: float | None
    rating: float | None
    n_reviews: int | None
    popularity: float | None
    store: str | None
    document: str = ""                    # embed_text — ไว้ตรวจว่าทำไมชิ้นนี้ถูกค้นเจอ
    anchor_score: float | None = None     # คะแนนเทียบ**คำถามเดิมของผู้ใช้**
                                          # ลูปของ A3/A3C เติมให้ในรอบที่ 2 ขึ้นไป
                                          # ใช้**จัดอันดับ** ไม่ใช้ผ่านประตู (ดู rerank)
    metadata: dict = field(default_factory=dict)

    def summary(self) -> str:
        price = f"${self.price:,.2f}" if self.price is not None else "ไม่ระบุราคา"
        reviews = f"{self.n_reviews:,} รีวิว" if self.n_reviews else "ไม่มีรีวิว"
        return (f"{self.title[:70]} · {price} · {self.rating} ดาว ({reviews}) "
                f"· {self.category}")


class Retriever:
    """ค้นสินค้าจากดัชนีเวกเตอร์ — ใช้ร่วมกันได้ทุกสถาปัตยกรรม"""

    def __init__(self, collection: str = COLLECTION, chroma_dir: Path = CHROMA_DIR):
        if not chroma_dir.exists():
            raise SystemExit(f"❌ ไม่พบ {chroma_dir} — รัน `python src\\build_index.py` ก่อน")
        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        names = [c.name for c in self._client.list_collections()]
        if collection not in names:
            raise SystemExit(f"❌ ไม่พบ collection '{collection}' (มี: {names})")
        self.collection = self._client.get_collection(collection)
        self._http = httpx.Client(timeout=120)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self._http.close()

    # ---------------------------------------------------------------- embedding

    def embed_query(self, text: str) -> list[float]:
        """แปลงคำค้นเป็นเวกเตอร์ด้วยโมเดล **ตัวเดียวกับที่ใช้แปลงสินค้า**

        ต้องเป็นโมเดลเดียวกันเท่านั้น — เวกเตอร์จากโมเดลต่างกันอยู่ในปริภูมิต่างกัน
        เอามาเทียบกันแล้วได้ผลที่ไร้ความหมาย ไม่ใช่แค่แย่ลง
        """
        response = self._http.post(f"{OLLAMA_URL}/api/embed",
                                   json={"model": MODEL, "input": [text]})
        response.raise_for_status()
        vectors = response.json().get("embeddings")
        if not vectors or len(vectors[0]) != DIM:
            raise RuntimeError(f"Ollama คืนเวกเตอร์ผิดรูป (คาด {DIM} มิติ)")
        return vectors[0]

    # ---------------------------------------------------------------- search

    def search(self, query: str, k: int = 10, where: dict | None = None) -> list[Hit]:
        """ค้นสินค้าด้วยข้อความ

        Args:
            query: คำค้น — **ภาษาอะไรก็ได้** (โมเดลรองรับหลายภาษา)
            k: จำนวนผลลัพธ์
            where: ตัวกรอง metadata ของ Chroma เช่น
                   `{"category": "Electronics"}` หรือ
                   `{"$and": [{"price_tier": "ถูก"}, {"average_rating": {"$gte": 4}}]}`
        """
        result = self.collection.query(
            query_embeddings=[self.embed_query(query)],
            n_results=k,
            where=where or None,
            include=["metadatas", "documents", "distances"],
        )
        return self._to_hits(result)

    def search_by_vector(self, vector: list[float], k: int = 10,
                         where: dict | None = None) -> list[Hit]:
        """ค้นด้วยเวกเตอร์ที่เตรียมมาแล้ว — ใช้เมื่อต้องยิงหลายคำค้นแล้วไม่อยาก encode ซ้ำ"""
        result = self.collection.query(
            query_embeddings=[vector], n_results=k, where=where or None,
            include=["metadatas", "documents", "distances"],
        )
        return self._to_hits(result)

    def score_against(self, ids: list[str],
                      vector: list[float]) -> dict[str, float]:
        """คะแนนความใกล้เคียงของสินค้าที่ระบุ **เทียบกับเวกเตอร์คำค้นที่ส่งมา**

        ใช้โดยลูปของ A3/A3C — รอบที่ 2 ขึ้นไปค้นด้วยคำค้นที่เขียนใหม่
        `Hit.score` ที่ได้จึงวัดความใกล้กับ*คำค้นใหม่* ไม่ใช่*สิ่งที่ผู้ใช้ขอ*
        ทำให้ประตูคัดเปิดกว้างขึ้นเรื่อย ๆ ตามที่คำค้นกว้างขึ้น
        (วัดได้จริง: คำค้นใหม่ทำให้ผ่านประตู 22 · 24 · 93 ชิ้น — ดู docs/steps.md ข้อ 234)

        เมธอดนี้คืนคะแนนเทียบ**เวกเตอร์หลัก** (คำถามเดิมของผู้ใช้) เพื่อให้ประตู
        ยังเป็นเกณฑ์สัมบูรณ์ที่ผูกกับสิ่งที่ผู้ใช้ขอ ไม่ใช่กับคำค้นล่าสุด

        คืน {parent_asin: คะแนน 0-1} · id ที่ดึงเวกเตอร์ไม่ได้จะไม่อยู่ใน dict

            >>> with Retriever() as r:
            ...     v = r.embed_query("claw hammer")
            ...     list(r.score_against(["B07VQJZ2K9"], v).values())[0] <= 1.0
            True
        """
        if not ids:
            return {}
        got = self.collection.get(ids=list(ids), include=["embeddings"])
        vecs = got.get("embeddings")
        if vecs is None or len(vecs) == 0:
            return {}
        q = np.asarray(vector, dtype=np.float32)
        m = np.asarray(vecs, dtype=np.float32)
        qn = float(np.linalg.norm(q))
        mn = np.linalg.norm(m, axis=1)
        if qn == 0.0:
            return {}
        safe = np.where(mn == 0.0, 1.0, mn)
        sims = (m @ q) / (safe * qn)
        return {doc_id: float(v) for doc_id, v, ok in zip(got["ids"], sims, mn > 0.0)
                if ok}

    def get(self, product_id: str) -> Hit | None:
        """ดึงสินค้าชิ้นเดียวด้วย parent_asin"""
        got = self.collection.get(ids=[product_id],
                                  include=["metadatas", "documents"])
        if not got["ids"]:
            return None
        return self._make_hit(got["ids"][0], got["metadatas"][0],
                              got["documents"][0], distance=0.0)

    def count(self) -> int:
        return self.collection.count()

    # ---------------------------------------------------------------- ภายใน

    @staticmethod
    def _make_hit(doc_id, meta: dict, document: str, distance: float) -> Hit:
        meta = meta or {}
        reviews = meta.get("rating_number")
        return Hit(
            id=doc_id,
            score=1.0 - distance,                 # Chroma คืน cosine distance
            title=str(meta.get("title", "")),
            category=str(meta.get("category", "")),
            price=meta.get("price"),
            rating=meta.get("average_rating"),
            n_reviews=int(reviews) if reviews is not None else None,
            popularity=meta.get("popularity"),
            store=meta.get("store"),
            document=document or "",
            metadata=meta,
        )

    def _to_hits(self, result: dict) -> list[Hit]:
        return [
            self._make_hit(doc_id, meta, document, distance)
            for doc_id, meta, document, distance in zip(
                result["ids"][0], result["metadatas"][0],
                result["documents"][0], result["distances"][0], strict=True)
        ]
