"""4-3 설정 한 곳 모으기.

주소·포트를 코드에 박지 않는다 (원칙 A).
우선순위: 환경변수 > config.json > 기본값.

- CM2_URL  : 4-2(Contentsmaker-2) 주소. 기본값 http://localhost:4005
- PORT     : 4-3 서버 포트. 기본값 8003
- BLENDER_PATH : blender.exe 경로 (비우면 자동 탐색)
"""
import os
import json
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULTS: Dict[str, Any] = {
    "cm2_url": "http://localhost:4005",
    "port": 8003,
    "storage_warn_clips": 40,
    "storage_warn_mb": 2048,
}


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


def _setting(key: str, env_name: str):
    env_value = os.environ.get(env_name)
    if env_value is not None and str(env_value).strip():
        return str(env_value).strip()
    value = load_config().get(key)
    if value is not None and str(value).strip():
        return value
    return DEFAULTS.get(key)


def get_cm2_url() -> str:
    """4-2 주소. 끝의 / 는 떼어 돌려준다."""
    return str(_setting("cm2_url", "CM2_URL")).rstrip("/")


def get_port() -> int:
    try:
        return int(_setting("port", "PORT"))
    except (TypeError, ValueError):
        return int(DEFAULTS["port"])


def get_storage_limits() -> Dict[str, int]:
    """보관 알림 기준. 넘으면 알리기만 하고 자동 삭제는 하지 않는다."""
    def _num(key, env_name):
        try:
            return int(_setting(key, env_name))
        except (TypeError, ValueError):
            return int(DEFAULTS[key])
    return {
        "clips": _num("storage_warn_clips", "STORAGE_WARN_CLIPS"),
        "mb": _num("storage_warn_mb", "STORAGE_WARN_MB"),
    }


if __name__ == "__main__":
    print(json.dumps({
        "config_file": str(CONFIG_FILE),
        "exists": CONFIG_FILE.exists(),
        "cm2_url": get_cm2_url(),
        "port": get_port(),
        "storage": get_storage_limits(),
    }, indent=2, ensure_ascii=False))
