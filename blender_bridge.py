import os
import sys
import subprocess
import time
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests

from blender_detector import find_blender, get_blender_info
from scene_generator import generate_bpy_script

BASE_DIR = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR = BASE_DIR / "temp"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

class BlenderBridge:
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def get_status(self) -> Dict[str, Any]:
        info = get_blender_info()
        return {
            "blender": info,
            "total_renders": len(self.list_renders()),
            "active_jobs": len([j for j in self.jobs.values() if j.get("status") == "rendering"])
        }

    def list_renders(self) -> List[Dict[str, Any]]:
        results = []
        if not OUTPUTS_DIR.exists():
            return results

        # Read metadata files
        for meta_file in sorted(OUTPUTS_DIR.glob("*_meta.json"), key=os.path.getmtime, reverse=True):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append(data)
            except Exception:
                pass
        return results

    def start_render_job(self, params: Dict[str, Any]) -> Dict[str, Any]:
        blender_path = find_blender()
        if not blender_path:
            return {
                "success": False,
                "error": "Blender가 설치되어 있지 않거나 경로를 찾을 수 없습니다. 설치 또는 설정이 필요합니다."
            }

        job_id = f"shot_{int(time.time())}"
        mp4_path = OUTPUTS_DIR / f"{job_id}.mp4"
        thumb_path = OUTPUTS_DIR / f"{job_id}_thumb.png"
        script_path = SCRIPTS_DIR / f"run_{job_id}.py"
        meta_path = OUTPUTS_DIR / f"{job_id}_meta.json"

        # Generate bpy script
        bpy_code = generate_bpy_script(params, str(mp4_path), str(thumb_path))
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(bpy_code)

        meta = {
            "job_id": job_id,
            "status": "rendering",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "params": params,
            "mp4_file": str(mp4_path.name),
            "thumb_file": str(thumb_path.name),
            "mp4_full_path": str(mp4_path),
            "thumb_full_path": str(thumb_path),
            "duration": params.get("duration", 4.0),
            "aspect_ratio": params.get("aspect_ratio", "16:9"),
            "logs": []
        }
        self.jobs[job_id] = meta

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # Launch Blender headless process
        cmd = [blender_path, "-b", "--python", str(script_path)]
        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            # Store process
            self.jobs[job_id]["process"] = p
            # Start background monitoring thread
            import threading
            def monitor():
                logs = []
                for line in p.stdout:
                    logs.append(line.strip())
                    if len(logs) > 200:
                        logs = logs[-200:]
                    self.jobs[job_id]["logs"] = logs

                p.wait()
                if p.returncode == 0 and mp4_path.exists():
                    self.jobs[job_id]["status"] = "completed"
                else:
                    self.jobs[job_id]["status"] = "failed"
                    self.jobs[job_id]["error"] = f"Blender exited with code {p.returncode}"

                # Update metadata
                meta_to_save = dict(self.jobs[job_id])
                meta_to_save.pop("process", None)
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_to_save, f, indent=2, ensure_ascii=False)

            t = threading.Thread(target=monitor, daemon=True)
            t.start()

            return {
                "success": True,
                "job_id": job_id,
                "status": "rendering",
                "message": "3D 씬 렌더링이 시작되었습니다."
            }
        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            return {"success": False, "error": str(e)}

    def open_in_explorer(self, file_path: Optional[str] = None):
        target = file_path if file_path and os.path.exists(file_path) else str(OUTPUTS_DIR)
        if sys.platform == "win32":
            if os.path.isfile(target):
                subprocess.run(["explorer.exe", f"/select,{target}"])
            else:
                subprocess.run(["explorer.exe", target])
        return {"success": True, "target": target}

    def send_to_contentsmaker_2(self, job_id: str, plan_id: str, slot: str = "scene_1", cm2_url: str = "http://localhost:8002") -> Dict[str, Any]:
        """Directly sends the rendered MP4 to Contentsmaker-2 via its /api/render/media endpoint."""
        mp4_path = OUTPUTS_DIR / f"{job_id}.mp4"
        if not mp4_path.exists():
            return {"success": False, "error": f"파일을 찾을 수 없습니다: {mp4_path}"}

        try:
            with open(mp4_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "plan_id": plan_id,
                "slot": slot,
                "filename": mp4_path.name,
                "data_base64": f"data:video/mp4;base64,{b64_data}"
            }

            resp = requests.post(f"{cm2_url}/api/render/media", json=payload, timeout=15)
            if resp.status_code == 200:
                return {"success": True, "message": f"4-2 씬({slot})에 블렌더 영상 장착 완료!", "response": resp.json()}
            else:
                return {"success": False, "error": f"4-2 응답 오류 ({resp.status_code}): {resp.text}"}
        except Exception as e:
            return {"success": False, "error": f"4-2 서버 연결 실패 ({cm2_url}): {e}"}

bridge = BlenderBridge()
