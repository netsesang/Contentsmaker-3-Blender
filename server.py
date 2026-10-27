import os
import sys
import socket
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from blender_detector import get_blender_info, save_config, load_config, detect_gpu, find_blender
from blender_bridge import bridge, OUTPUTS_DIR

app = FastAPI(title="Contentsmaker-3-Blender", description="Blender 3D Video Studio for Contentsmaker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RenderRequest(BaseModel):
    building_style: str = Field(default="modern_tower", description="modern_tower, cyberpunk_block, minimal_pavilion")
    floors: int = Field(default=16, ge=3, le=40)
    lighting: str = Field(default="cinematic_sunset", description="cinematic_sunset, cyberpunk_neon, studio_clean")
    camera_shot: str = Field(default="orbit_360", description="orbit_360, tilt_up, push_in, pan_lateral")
    aspect_ratio: str = Field(default="16:9", description="16:9 or 9:16")
    duration: float = Field(default=4.0, ge=1.0, le=30.0)
    engine: str = Field(default="CYCLES", description="CYCLES (Raytracing) or EEVEE")
    volumetric: bool = Field(default=True, description="Enable volumetric fog and light rays")
    fstop: float = Field(default=1.8, ge=0.5, le=22.0, description="Camera aperture for bokeh")
    samples: int = Field(default=96, ge=16, le=512, description="Cycles render samples")
    fps: int = Field(default=30, ge=15, le=60)

class ConfigRequest(BaseModel):
    blender_path: str

class SendToCM2Request(BaseModel):
    job_id: str
    plan_id: str
    slot: str = "1"                       # 4-2 는 '1'~'N' 또는 'thumbnail' 만 받는다
    cm2_url: Optional[str] = None         # 비우면 config.json / CM2_URL 환경변수 (기본 4005)

class OpenExplorerRequest(BaseModel):
    file_path: Optional[str] = None

@app.get("/api/status")
def get_status():
    status = bridge.get_status()
    bridge.write_report()
    return status

@app.get("/api/report")
def get_report():
    return bridge.write_report()

@app.post("/api/config")
def update_config(req: ConfigRequest):
    if not os.path.isfile(req.blender_path):
        raise HTTPException(status_code=400, detail=f"지정한 파일이 존재하지 않습니다: {req.blender_path}")
    cfg = load_config()
    cfg["blender_path"] = req.blender_path
    save_config(cfg)
    return {"success": True, "info": get_blender_info()}

@app.post("/api/render")
def trigger_render(req: RenderRequest):
    res = bridge.start_render_job(req.dict())
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.get("/api/jobs")
def get_jobs():
    return {
        job_id: {
            "status": data.get("status"),
            "created_at": data.get("created_at"),
            "seconds": data.get("seconds"),
            "params": data.get("params"),
            "mp4_file": data.get("mp4_file"),
            "thumb_file": data.get("thumb_file"),
            "error": data.get("error"),
            "recent_logs": (data.get("logs") or [])[-15:]
        }
        for job_id, data in bridge.jobs.items()
    }

@app.get("/api/renders")
def get_renders():
    return bridge.list_renders()

@app.get("/api/renders/{filename}")
def get_render_file(filename: str):
    file_path = OUTPUTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    media_type = "video/mp4" if filename.endswith(".mp4") else "image/png"
    return FileResponse(file_path, media_type=media_type)

@app.post("/api/open-folder")
def open_folder(req: OpenExplorerRequest):
    return bridge.open_in_explorer(req.file_path)

@app.post("/api/send-to-contentsmaker2")
def send_to_cm2(req: SendToCM2Request):
    res = bridge.send_to_contentsmaker_2(req.job_id, req.plan_id, req.slot, req.cm2_url)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

# Static files for modern Web UI
WEB_DIR = Path(__file__).parent / "web"
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

@app.get("/")
def serve_root():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Contentsmaker-3-Blender API is running."}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    def warm_up():
        # GPU 가속 여부는 블렌더에게 직접 물어본다 (몇 초 걸리므로 뒤에서 한 번만).
        path = find_blender()
        if path:
            detect_gpu(path)
        bridge.write_report()
    threading.Thread(target=warm_up, daemon=True).start()
    yield
    # 서버를 끄면 「쉬는 중」으로 남긴다 (98번이 멈춤으로 오해하지 않게).
    bridge.write_report(state="idle")


app.router.lifespan_context = lifespan


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """이미 누가 쓰고 있는지만 본다. 남의 서버는 절대 끄지 않는다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    port = config.get_port()
    if port_in_use(port):
        print(f"[멈춤] 포트 {port} 가 이미 쓰이고 있습니다.")
        print("       이미 켜져 있는 그 서버는 끄지 않았습니다.")
        print(f"       - 4-3 이 이미 떠 있다면 브라우저에서 http://localhost:{port} 를 열어 쓰십시오.")
        print(f"       - 다른 프로그램이 쓰고 있다면 다른 포트로 켜십시오:  set PORT=8013 && python server.py")
        print("       - 또는 config.json 의 \"port\" 값을 바꾸십시오.")
        sys.exit(1)
    print(f"Starting Contentsmaker-3-Blender Studio on port {port}...  (4-2 주소: {config.get_cm2_url()})")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
