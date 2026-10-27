import sys
import json
import os
from pathlib import Path

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

import config
from blender_bridge import bridge
from blender_detector import get_blender_info

TOOLS = [
    {
        "name": "get_blender_status",
        "description": "Blender 설치 경로, 버전, GPU 가속 지원 여부 및 현재 렌더링 작업 상태를 확인합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "render_3d_shot",
        "description": "Blender 3D를 제어하여 건물 3D 모델, 조명, 3D 캐릭터, 카메라 무빙을 설정하고 MP4 영상 및 썸네일을 로컬 GPU로 0원에 렌더링합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "building_style": {
                    "type": "string",
                    "enum": ["modern_tower", "cyberpunk_block", "minimal_pavilion"],
                    "description": "건물 스타일 (modern_tower: 현대식 고층 유리 타워, cyberpunk_block: 사이버펑크 블록, minimal_pavilion: 미니멀 파빌리온)"
                },
                "floors": {
                    "type": "integer",
                    "default": 12,
                    "description": "건물 층수 (예: 6 ~ 24)"
                },
                "lighting": {
                    "type": "string",
                    "enum": ["cinematic_sunset", "cyberpunk_neon", "studio_clean"],
                    "default": "cinematic_sunset",
                    "description": "조명 분위기 (cinematic_sunset: 황금빛 일몰+블루 림라이트, cyberpunk_neon: 네온 사이안/마젠타, studio_clean: 밝고 선명한 스튜디오광)"
                },
                "camera_shot": {
                    "type": "string",
                    "enum": ["orbit_360", "tilt_up", "push_in", "pan_lateral"],
                    "default": "orbit_360",
                    "description": "카메라 무빙 (orbit_360: 건물 주변 회전, tilt_up: 지상에서 옥상으로 틸트업(쇼츠 추천), push_in: 캐릭터/창가로 줌인, pan_lateral: 수평 이동)"
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["16:9", "9:16"],
                    "default": "16:9",
                    "description": "화면비 (16:9 가로형 유튜브, 9:16 세로형 쇼츠/릴스)"
                },
                "duration": {
                    "type": "number",
                    "default": 4.0,
                    "description": "클립 길이 (초 단위, 예: 4.0 ~ 8.0)"
                },
                "engine": {
                    "type": "string",
                    "enum": ["CYCLES", "EEVEE"],
                    "default": "CYCLES",
                    "description": "렌더 엔진 (CYCLES: 영화 CG급 OptiX 레이트레이싱, EEVEE: 고속 프리뷰)"
                },
                "volumetric": {
                    "type": "boolean",
                    "default": True,
                    "description": "대기 볼류메트릭 안개 및 빛내림(God Rays) 활성화 여부"
                },
                "fstop": {
                    "type": "number",
                    "default": 1.8,
                    "description": "카메라 조리개값 (1.8: 영화 렌즈 보케 아웃포커싱, 8.0: 전체 선명)"
                }
            }
        }
    },
    {
        "name": "list_rendered_clips",
        "description": "렌더링 완료된 3D MP4 클립 및 썸네일 목록을 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "send_to_contentsmaker2",
        "description": "렌더링된 3D 클립(mp4)을 Contentsmaker-2(4-2)의 씬 카드로 직접 전송 주입합니다. 슬롯이 'thumbnail' 이면 mp4 대신 썸네일 png 를 보냅니다.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id", "plan_id", "slot"],
            "properties": {
                "job_id": { "type": "string", "description": "렌더링 클립 ID (예: shot_1712345678)" },
                "plan_id": { "type": "string", "description": "Contentsmaker-2의 기획안 ID" },
                "slot": { "type": "string", "description": "장착할 씬 슬롯. 4-2 는 씬 번호 문자열('1', '2', '3' …) 또는 'thumbnail' 만 받는다. 'scene_1' 같은 표기는 거절된다" },
                "cm2_url": { "type": "string", "description": "Contentsmaker-2 서버 주소. 비우면 config.json / 환경변수 CM2_URL 의 값(기본 http://localhost:4005)을 쓴다" }
            }
        }
    }
]

def handle_rpc(request: dict) -> dict:
    method = request.get("method")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": { "tools": {} },
                "serverInfo": {
                    "name": "contentsmaker-blender-mcp",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": { "tools": TOOLS }
        }

    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "get_blender_status":
                res = bridge.get_status()
            elif tool_name == "render_3d_shot":
                res = bridge.start_render_job(args)
            elif tool_name == "list_rendered_clips":
                res = bridge.list_renders()
            elif tool_name == "send_to_contentsmaker2":
                res = bridge.send_to_contentsmaker_2(
                    args.get("job_id"),
                    args.get("plan_id"),
                    args.get("slot", "1"),
                    args.get("cm2_url") or config.get_cm2_url()
                )
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": { "code": -32601, "message": f"Method {tool_name} not found" }
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        { "type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2) }
                    ]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        { "type": "text", "text": f"Error executing tool: {e}" }
                    ],
                    "isError": True
                }
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": { "code": -32601, "message": f"Unhandled method {method}" }
    }

def main():
    """Reads JSON-RPC lines from stdin and writes responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_rpc(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": { "code": -32700, "message": f"Parse error: {e}" }
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
