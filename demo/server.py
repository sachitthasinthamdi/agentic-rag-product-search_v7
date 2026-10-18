"""เซิร์ฟเวอร์สาธิต — เลือกสถาปัตยกรรม A1 / A3C / A3 ได้ในหน้าเดียว

ใช้ไลบรารีมาตรฐานของ Python เท่านั้น ไม่ต้องติดตั้งเว็บเฟรมเวิร์กเพิ่ม

⚠ ต้องเปิด Ollama ก่อน:  ollama serve

รัน:  .venv\\Scripts\\python.exe demo\\server.py
      แล้วเปิด http://127.0.0.1:8000

เส้นทาง
    GET  /            หน้าเว็บ
    POST /api/ask     {"arm": "A1", "message": "..."}  หรือ
                      {"arms": ["A1","A3C","A3"], "message": "..."}
    POST /api/reset   {"arm": "A1"}  หรือ {}  เพื่อล้างความจำทุกแขน
"""
from __future__ import annotations

import io
import json
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

HOST, PORT = "127.0.0.1", 8000
PAGE = Path(__file__).resolve().parent / "index.html"

ARM_ORDER = ("A1", "A3C", "A3")
ARM_LABEL = {
    "A1":  "RAG มาตรฐาน — ไม่มีชั้นตัดสินใจ ค้นรอบเดียว",
    "A3C": "Agentic RAG — เอเจนต์เลือกการกระทำ กฎในโปรแกรมคุมการค้นซ้ำ",
    "A3":  "Agentic RAG — เอเจนต์เลือกการกระทำและคุมการค้นซ้ำเอง",
}

# สร้างตัวระบบตอนใช้ครั้งแรกเท่านั้น เพราะแต่ละตัวเปิดการเชื่อมต่อฐานข้อมูลเวกเตอร์
_arms: dict = {}
_lock = Lock()


def get_arm(name: str):
    """คืนตัวระบบของแขนนั้น สร้างใหม่ถ้ายังไม่เคยใช้

    แต่ละแขนเก็บความจำของตัวเองแยกกัน จึงเทียบกันได้อย่างเป็นธรรม
    """
    if name not in ARM_LABEL:
        raise ValueError(f"ไม่รู้จักแขน {name!r}")
    with _lock:
        if name not in _arms:
            if name == "A1":
                from a1 import A1
                _arms[name] = A1()
            elif name == "A3C":
                from a3c import A3C
                _arms[name] = A3C()
            else:
                from a3 import A3
                _arms[name] = A3()
        return _arms[name]


def reset_arm(name: str | None = None) -> None:
    with _lock:
        if name is None:
            _arms.clear()
        else:
            _arms.pop(name, None)


def product(hit) -> dict:
    return {
        "title":     hit.title,
        "price":     hit.price,
        "rating":    hit.rating,
        "n_reviews": hit.n_reviews,
        "store":     hit.store,
        "score":     round(hit.score, 4) if hit.score is not None else None,
    }


def summarize(trace: dict) -> dict:
    """ดึงเฉพาะตัวเลขที่ใช้เทียบสถาปัตยกรรม ไม่ส่ง trace ดิบทั้งก้อน"""
    rr = trace.get("rerank") or {}
    return {
        "llm_calls":    trace.get("llm_calls"),
        "n_searches":   trace.get("n_searches"),
        "n_candidates": rr.get("n_candidates"),
        "n_passed":     rr.get("n_passed"),
        "language":     trace.get("language"),
        "action":       (trace.get("planner") or {}).get("action"),
        "tried":        trace.get("tried_queries") or trace.get("search_texts"),
        "stop_reason":  trace.get("stop_reason"),
    }


def ask(arm_name: str, message: str) -> dict:
    started = time.time()
    try:
        turn = get_arm(arm_name).respond(message)
    except Exception as exc:                                   # noqa: BLE001
        traceback.print_exc()
        hint = ""
        if "refused" in str(exc).lower() or "connect" in str(exc).lower():
            hint = " — ตรวจว่าเปิด Ollama แล้วหรือยัง (ollama serve)"
        return {"arm": arm_name, "label": ARM_LABEL[arm_name],
                "error": f"{type(exc).__name__}: {exc}{hint}",
                "seconds": round(time.time() - started, 1)}
    return {
        "arm":      arm_name,
        "label":    ARM_LABEL[arm_name],
        "reply":    turn.reply,
        "products": [product(h) for h in turn.hits],
        "trace":    summarize(turn.trace),
        "seconds":  round(time.time() - started, 1),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):                          # เงียบ log ปกติ
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "ไม่พบหน้านี้"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "อ่าน JSON ไม่ได้"})

        if self.path == "/api/reset":
            reset_arm(data.get("arm"))
            return self._json(200, {"ok": True})

        if self.path != "/api/ask":
            return self._json(404, {"error": "ไม่พบเส้นทางนี้"})

        message = (data.get("message") or "").strip()
        if not message:
            return self._json(400, {"error": "ยังไม่ได้พิมพ์คำถาม"})

        arms = data.get("arms") or [data.get("arm") or "A1"]
        arms = [a for a in ARM_ORDER if a in arms]              # เรียงให้คงที่เสมอ
        if not arms:
            return self._json(400, {"error": "ยังไม่ได้เลือกสถาปัตยกรรม"})

        print(f"  ถาม [{' '.join(arms)}] : {message}")
        results = [ask(a, message) for a in arms]
        for r in results:
            mark = "ผิดพลาด" if r.get("error") else f"{r['seconds']} วินาที"
            print(f"    {r['arm']:4} {mark}")
        return self._json(200, {"results": results})


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if not PAGE.exists():
        sys.exit(f"ไม่พบไฟล์หน้าเว็บ {PAGE}")
    print("เซิร์ฟเวอร์สาธิตพร้อมแล้ว")
    print(f"  เปิดที่  http://{HOST}:{PORT}")
    print("  ⚠ ต้องเปิด Ollama ไว้ด้วย (ollama serve)")
    print("  กด Ctrl+C เพื่อหยุด\n")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nหยุดเซิร์ฟเวอร์แล้ว")


if __name__ == "__main__":
    main()
