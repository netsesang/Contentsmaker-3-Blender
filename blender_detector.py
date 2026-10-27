import os
import glob
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from config import CONFIG_FILE, load_config, save_config  # 설정은 config.py 한 곳에서

DEFAULT_SEARCH_PATHS = [
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
    r"D:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"D:\SteamLibrary\steamapps\common\Blender\blender.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe"),
]

# GPU 조사는 블렌더를 한 번 띄워야 해서 느리다. 프로세스가 사는 동안 한 번만 한다.
_gpu_cache: Dict[str, Any] = {}


def searched_paths() -> List[str]:
    """블렌더를 찾아본 자리 목록 (사람에게 보여 주려고 쓴다)."""
    return [
        "환경변수 BLENDER_PATH",
        f"설정 파일 {CONFIG_FILE} 의 blender_path",
        "PATH 환경변수 (where blender)",
    ] + list(DEFAULT_SEARCH_PATHS)


def find_blender() -> Optional[str]:
    """Finds blender.exe path from env, config, PATH, or default paths."""
    env_path = os.environ.get("BLENDER_PATH", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path

    config = load_config()
    custom_path = config.get("blender_path")
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    # Check PATH environment variable
    try:
        res = subprocess.run(["where.exe", "blender"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            for line in lines:
                if os.path.isfile(line.strip()):
                    return line.strip()
    except Exception:
        pass

    # Search common Windows directories
    for pattern in DEFAULT_SEARCH_PATHS:
        matches = glob.glob(pattern)
        if matches:
            # Sort descending to pick the newest version (e.g. Blender 4.5 > 4.2)
            matches.sort(reverse=True)
            for m in matches:
                if os.path.isfile(m):
                    return m

    return None


def detect_gpu(blender_path: str, timeout: int = 60) -> Dict[str, Any]:
    """Cycles 가 쓸 수 있는 GPU 를 블렌더에게 직접 물어본다.

    돌려주는 값의 `accelerated` 는 True / False / None(모름) 세 가지다.
    모르면 None 이다 — 지어내지 않는다.
    """
    if blender_path in _gpu_cache:
        return _gpu_cache[blender_path]

    result: Dict[str, Any] = {"accelerated": None, "backend": None, "devices": [], "message": "GPU 가속 여부를 확인하지 못했습니다."}
    expr = (
        "import bpy,json;"
        "p=bpy.context.preferences.addons['cycles'].preferences;"
        "f=[(t,[d.name for d in p.get_devices_for_type(t) if d.type==t]) for t in ('OPTIX','CUDA','HIP','ONEAPI','METAL')];"
        "print('GPUPROBE:'+json.dumps([x for x in f if x[1]]))"
    )
    try:
        res = subprocess.run(
            [blender_path, "-b", "--factory-startup", "--python-expr", expr],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
        for line in (res.stdout or "").splitlines():
            if line.startswith("GPUPROBE:"):
                found = json.loads(line[len("GPUPROBE:"):])
                if found:
                    backend, devices = found[0]
                    result = {
                        "accelerated": True,
                        "backend": backend,
                        "devices": devices,
                        "message": f"{backend} GPU 가속 사용 가능: {', '.join(devices)}",
                    }
                else:
                    result = {
                        "accelerated": False,
                        "backend": None,
                        "devices": [],
                        "message": "Cycles 가 쓸 수 있는 GPU 를 찾지 못했습니다 (CPU 로 렌더합니다).",
                    }
                break
    except Exception:
        pass

    _gpu_cache[blender_path] = result
    return result


def get_blender_info(probe_gpu: bool = False) -> Dict[str, Any]:
    blender_path = find_blender()
    if not blender_path:
        return {
            "installed": False,
            "path": None,
            "version": None,
            "gpu_detected": None,
            "gpu": {"accelerated": None, "backend": None, "devices": [], "message": "블렌더가 없어 GPU 를 확인할 수 없습니다."},
            "searched_paths": searched_paths(),
            "message": (
                "블렌더를 찾을 수 없습니다. 블렌더를 설치하시거나, 화면의 [블렌더 경로 지정]에 "
                "blender.exe 위치를 넣어 주십시오. 아래 자리를 찾아봤습니다."
            ),
        }

    version_str = "Unknown"
    try:
        res = subprocess.run([blender_path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8)
        if res.returncode == 0:
            # First line: e.g. Blender 4.2.0 (sub 0)
            lines = res.stdout.strip().splitlines()
            if lines:
                version_str = lines[0].strip()
    except Exception as e:
        version_str = f"Error: {e}"

    gpu = detect_gpu(blender_path) if probe_gpu else _gpu_cache.get(
        blender_path, {"accelerated": None, "backend": None, "devices": [], "message": "아직 확인하지 않았습니다."}
    )

    return {
        "installed": True,
        "path": blender_path,
        "version": version_str,
        "gpu_detected": gpu.get("accelerated"),
        "gpu": gpu,
        "searched_paths": searched_paths(),
        "message": "블렌더 정상 감지됨",
    }


if __name__ == "__main__":
    info = get_blender_info(probe_gpu=True)
    print(json.dumps(info, indent=2, ensure_ascii=False))
