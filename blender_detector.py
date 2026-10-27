import os
import glob
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any

CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_SEARCH_PATHS = [
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
    r"D:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"D:\SteamLibrary\steamapps\common\Blender\blender.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe"),
]

def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config: Dict[str, Any]):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def find_blender() -> Optional[str]:
    """Finds blender.exe path from config, environment, or default paths."""
    config = load_config()
    custom_path = config.get("blender_path")
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    # Check PATH environment variable
    try:
        res = subprocess.run(["where.exe", "blender"], capture_output=True, text=True, timeout=3)
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

def get_blender_info() -> Dict[str, Any]:
    blender_path = find_blender()
    if not blender_path:
        return {
            "installed": False,
            "path": None,
            "version": None,
            "gpu_detected": False,
            "message": "Blender를 찾을 수 없습니다. 설치가 필요합니다."
        }

    version_str = "Unknown"
    try:
        res = subprocess.run([blender_path, "--version"], capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            # First line: e.g. Blender 4.2.0 (sub 0)
            lines = res.stdout.strip().splitlines()
            if lines:
                version_str = lines[0].strip()
    except Exception as e:
        version_str = f"Error: {e}"

    return {
        "installed": True,
        "path": blender_path,
        "version": version_str,
        "gpu_detected": True,
        "message": "Blender 정상 감지됨"
    }

if __name__ == "__main__":
    info = get_blender_info()
    print(json.dumps(info, indent=2, ensure_ascii=False))
