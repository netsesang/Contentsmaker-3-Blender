import os
import sys
import subprocess
import time
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import requests

import config
from blender_detector import find_blender, get_blender_info
from scene_generator import generate_bpy_script

BASE_DIR = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR = BASE_DIR / "temp"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# 4-2 가 알아보는 슬롯: '1' ~ 'N' 또는 'thumbnail' (근거: 4-2 producer.py save_media 주석/구현)
SLOT_HELP = "씬 번호(1, 2, 3 …) 또는 thumbnail 을 넣으십시오."
MAX_SLOT = 99
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm"}


def normalize_slot(slot: Any) -> Tuple[Optional[str], Optional[str]]:
    """슬롯 값을 4-2 표기로 바꾼다. 돌려주는 값: (슬롯, 오류말). 둘 중 하나는 None.

    4-2 는 'scene_1' 같은 표기를 받지 않는다 — 보내기 전에 여기서 막는다.
    """
    text = str(slot if slot is not None else "").strip()
    if not text:
        return None, f"슬롯이 비어 있습니다. {SLOT_HELP}"

    if text.lower() == "thumbnail":
        return "thumbnail", None

    if text.isdigit():
        number = int(text)
        if 1 <= number <= MAX_SLOT:
            return str(number), None
        return None, f"씬 번호는 1 부터 {MAX_SLOT} 까지입니다 (받은 값: {text})."

    hint = ""
    if text.lower().startswith("scene_") and text[6:].isdigit():
        hint = f" '{text}' 이(가) 아니라 '{text[6:]}' 라고 쓰십시오."
    return None, f"4-2 가 알아보지 못하는 슬롯입니다: '{text}'. {SLOT_HELP}{hint}"


def check_slot_file(slot: str, filename: str) -> Optional[str]:
    """슬롯과 파일 종류가 맞는지 본다. 맞으면 None, 아니면 사람이 읽는 오류말."""
    ext = Path(filename).suffix.lower()
    if slot == "thumbnail":
        if ext not in IMAGE_EXTS:
            return (
                f"썸네일 칸에는 이미지(png·jpg)만 들어갑니다 — 보내려는 파일은 '{ext or '확장자 없음'}' 입니다. "
                "영상은 씬 번호(1, 2, 3 …) 칸으로 보내십시오."
            )
        return None
    if ext not in VIDEO_EXTS and ext not in IMAGE_EXTS:
        return f"4-2 는 영상(mp4·mov·webm) 또는 이미지(png·jpg·webp)만 받습니다 — 보내려는 파일은 '{ext or '확장자 없음'}' 입니다."
    return None


class BlenderBridge:
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def get_status(self) -> Dict[str, Any]:
        info = get_blender_info()
        renders = self.list_renders()
        return {
            "blender": info,
            "total_renders": len(renders),
            "active_jobs": len([j for j in self.jobs.values() if j.get("status") == "rendering"]),
            "cm2_url": config.get_cm2_url(),
            "storage": self.storage_status(),
        }

    # ── 보관 한도 (알림까지만, 자동 삭제는 하지 않는다) ─────────────────
    def storage_status(self) -> Dict[str, Any]:
        limits = config.get_storage_limits()
        clips = 0
        total_bytes = 0
        oldest = None
        if OUTPUTS_DIR.exists():
            for f in OUTPUTS_DIR.iterdir():
                if not f.is_file():
                    continue
                total_bytes += f.stat().st_size
                if f.suffix.lower() == ".mp4":
                    clips += 1
                    mtime = f.stat().st_mtime
                    if oldest is None or mtime < oldest[1]:
                        oldest = (f.name, mtime)

        mb = round(total_bytes / (1024 * 1024), 1)
        over_clips = clips >= limits["clips"]
        over_mb = mb >= limits["mb"]
        warning = None
        if over_clips or over_mb:
            warning = (
                f"outputs 폴더에 클립 {clips}개 · {mb}MB 가 쌓였습니다 "
                f"(알림 기준 {limits['clips']}개 · {limits['mb']}MB). "
                "필요 없는 것은 직접 지워 주십시오 — 4-3 은 자동으로 지우지 않습니다."
            )
        return {
            "clips": clips,
            "megabytes": mb,
            "limit_clips": limits["clips"],
            "limit_megabytes": limits["mb"],
            "over_limit": bool(warning),
            "oldest_clip": oldest[0] if oldest else None,
            "warning": warning,
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
            info = get_blender_info()
            return {
                "success": False,
                "error": info["message"],
                "searched_paths": info["searched_paths"],
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

        started_at = time.time()
        meta = {
            "job_id": job_id,
            "status": "rendering",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "started_epoch": started_at,
            "finished_at": None,
            "seconds": None,
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
                self.jobs[job_id]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.jobs[job_id]["seconds"] = round(time.time() - started_at, 1)
                if p.returncode == 0 and mp4_path.exists():
                    self.jobs[job_id]["status"] = "completed"
                else:
                    self.jobs[job_id]["status"] = "failed"
                    self.jobs[job_id]["error"] = f"블렌더가 비정상 종료했습니다 (종료 코드 {p.returncode}). 화면의 진행 기록(log)을 확인해 주십시오."

                # Update metadata
                meta_to_save = dict(self.jobs[job_id])
                meta_to_save.pop("process", None)
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_to_save, f, indent=2, ensure_ascii=False)

                self.write_report()

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
            self.jobs[job_id]["error"] = f"블렌더를 실행하지 못했습니다: {e}"
            self.write_report()
            return {"success": False, "error": self.jobs[job_id]["error"]}

    def write_report(self, **kwargs):
        """report/report.json 갱신. 보고가 실패해도 렌더는 멈추지 않는다."""
        try:
            import report_writer
            return report_writer.write_report(self, **kwargs)
        except Exception:
            return None

    def open_in_explorer(self, file_path: Optional[str] = None):
        target = file_path if file_path and os.path.exists(file_path) else str(OUTPUTS_DIR)
        if sys.platform == "win32":
            if os.path.isfile(target):
                subprocess.run(["explorer.exe", f"/select,{target}"])
            else:
                subprocess.run(["explorer.exe", target])
        return {"success": True, "target": target}

    def send_to_contentsmaker_2(self, job_id: str, plan_id: str, slot: str = "1",
                                cm2_url: Optional[str] = None) -> Dict[str, Any]:
        """렌더한 파일을 4-2 의 입구(/api/render/media) 하나로 보낸다.

        슬롯은 보내기 전에 검사한다 — 4-2 는 '1'~'N' 또는 'thumbnail' 만 받는다.
        썸네일 칸에는 png, 씬 번호 칸에는 mp4 를 보낸다.
        """
        cm2_url = (cm2_url or config.get_cm2_url()).rstrip("/")

        if not str(plan_id or "").strip():
            return {"success": False, "error": "4-2 의 기획안 ID(plan_id)를 넣어 주십시오."}

        slot_value, slot_error = normalize_slot(slot)
        if slot_error:
            return {"success": False, "error": slot_error}

        if slot_value == "thumbnail":
            media_path = OUTPUTS_DIR / f"{job_id}_thumb.png"
            mime = "image/png"
        else:
            media_path = OUTPUTS_DIR / f"{job_id}.mp4"
            mime = "video/mp4"

        file_error = check_slot_file(slot_value, media_path.name)
        if file_error:
            return {"success": False, "error": file_error}

        if not media_path.exists():
            return {"success": False, "error": f"보낼 파일이 없습니다: {media_path.name} (렌더가 끝났는지 확인해 주십시오)"}

        try:
            with open(media_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return {"success": False, "error": f"파일을 읽지 못했습니다: {media_path.name}", "detail": str(e)}

        payload = {
            "plan_id": plan_id,
            "slot": slot_value,
            "filename": media_path.name,
            "data_base64": f"data:{mime};base64,{b64_data}"
        }

        try:
            resp = requests.post(f"{cm2_url}/api/render/media", json=payload, timeout=120)
        except requests.exceptions.ConnectionError as e:
            return {
                "success": False,
                "error": f"4-2({cm2_url})가 꺼져 있습니다 — 4-2 폴더의 run.bat 으로 켜신 뒤 다시 보내 주십시오.",
                "detail": str(e),
            }
        except requests.exceptions.Timeout as e:
            return {
                "success": False,
                "error": f"4-2({cm2_url})가 제때 답하지 않았습니다. 4-2 가 다른 일을 하고 있는지 확인한 뒤 다시 보내 주십시오.",
                "detail": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"4-2({cm2_url})로 보내는 중 문제가 생겼습니다. 주소가 맞는지 확인해 주십시오.",
                "detail": str(e),
            }

        if resp.status_code == 200:
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text[:300]}
            if isinstance(body, dict) and body.get("error"):
                return {"success": False, "error": f"4-2 가 거절했습니다: {body['error']}"}
            name = "썸네일" if slot_value == "thumbnail" else f"씬 {slot_value}"
            return {
                "success": True,
                "message": f"4-2 {name} 칸에 {media_path.name} 을(를) 넣었습니다.",
                "slot": slot_value,
                "cm2_url": cm2_url,
                "response": body,
            }

        reason = ""
        try:
            reason = (resp.json() or {}).get("error", "")
        except Exception:
            reason = (resp.text or "")[:200]
        return {
            "success": False,
            "error": f"4-2 가 받지 않았습니다 (응답 코드 {resp.status_code}){': ' + reason if reason else ''}",
        }


bridge = BlenderBridge()
