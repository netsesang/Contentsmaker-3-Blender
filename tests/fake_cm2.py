"""시험용 가짜 4-2 서버.

진짜 4-2(Contentsmaker-2)를 켜지 않고도 직송 길을 시험하려고 만든 것이다.
4-2 의 입구(`/api/render/media`)가 하는 일을 그대로 흉내 낸다 —
특히 **슬롯 규칙**(`'1'`~`'N'` 또는 `'thumbnail'`, 썸네일은 이미지만)까지 같게 했다.
근거: 4-2 `producer.py` `save_media()` · `server.py` 의 `/api/render/media`.

4-2 폴더는 읽기만 했고 고치지 않았다. 여기에 저장되는 파일은 임시 폴더로 간다.
"""
import base64
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm"}


class FakeCm2Handler(BaseHTTPRequestHandler):
    save_dir = None
    received = []

    def log_message(self, *args):
        pass  # 시험 중 콘솔을 더럽히지 않는다

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        if self.path != "/api/render/media":
            self._json({"error": "Not Found"}, 404)
            return
        try:
            data = json.loads(raw.decode("utf-8"))
            b64 = data.get("data_base64") or ""
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            if not b64:
                raise ValueError("파일 데이터가 없습니다.")
            payload = base64.b64decode(b64)

            slot = str(data.get("slot"))
            filename = data.get("filename") or ""
            ext = os.path.splitext(filename)[1].lower()
            if ext in IMAGE_EXTS:
                kind = "image"
            elif ext in VIDEO_EXTS:
                kind = "video"
            else:
                raise ValueError("이미지(png/jpg/webp) 또는 영상(mp4/mov/webm) 파일만 넣을 수 있습니다.")
            if slot == "thumbnail" and kind != "image":
                raise ValueError("썸네일은 이미지 파일이어야 합니다.")

            # 4-2 와 같은 이름 규칙 — 숫자가 아니면 여기서 ValueError 가 난다
            name = "thumbnail" if slot == "thumbnail" else "scene_%02d" % int(slot)
            out = os.path.join(self.save_dir, name + ext)
            with open(out, "wb") as f:
                f.write(payload)

            FakeCm2Handler.received.append({"plan_id": data.get("plan_id"), "slot": slot, "file": os.path.basename(out)})
            self._json({"status": "success", "item": {"slot": slot, "type": kind, "source": "upload"},
                        "media": {slot: {"type": kind, "file": os.path.basename(out)}}})
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # pragma: no cover
            self._json({"error": f"서버 오류: {e}"}, 500)


def start(save_dir):
    """가짜 4-2 를 띄우고 (주소, 끄는 함수) 를 돌려준다."""
    FakeCm2Handler.save_dir = save_dir
    FakeCm2Handler.received = []
    server = HTTPServer(("127.0.0.1", 0), FakeCm2Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    def stop():
        server.shutdown()
        server.server_close()

    return url, stop
