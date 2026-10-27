# Contentsmaker-3-Blender (4-3)

> **0원 원칙(Local GPU)** 기반 3D 씬 영상 제작 및 MCP 연계 스튜디오.  
> Blender 3D의 파워풀한 모델링·라이팅·카메라 연출을 통해 3D 건물, 조명 연출, 3D 캐릭터 씬을 생성하고, **장면 클립(MP4) 및 썸네일(PNG)**을 렌더링하여 **Contentsmaker-2(4-2)**에 원클릭으로 장착합니다.

---

## ⚡ 핵심 특징 및 원칙

1. **독립된 4-3 프로젝트**:
   - `Contentsmaker-2`와 분리된 자체 가상환경(`.venv`), 독립 포트(`8003`), 독립 저장소 유지
   - `.blend`, 대용량 캐시, 렌더 비디오는 `.gitignore`로 제외하여 백업 및 Git 비대화 방지
2. **비용 0원 (RTX GPU 로컬 가속)**:
   - 외부 유료 AI 영상 생성 API(Gemini/Sora/Runway 등) 대신, 로컬 RTX GPU(EEVEE/Cycles)로 1편당 $0 비용 렌더링
3. **4-2(Contentsmaker-2)와의 단일 접점**:
   - 4-3은 **장면 클립(MP4) + 썸네일(PNG)**만 정확하게 생성
   - 나레이션(TTS), 자막 합성, 음악, 유튜브 업로드는 4-2의 기존 파이프라인 활용
   - **드래그앤드롭**: 파일 탐색기(📁) 버튼으로 4-2 씬 카드에 즉시 드래그
   - **직송 API**: 기획안 ID와 씬 번호 입력 시 4-2로 다이렉트 주입
4. **Model Context Protocol (MCP) 탑재**:
   - `mcp_server.py`: AI 에이전트(Claude Desktop, Antigravity 등)가 자연어로 3D 건물을 짓고 카메라를 돌려 동영상을 추출할 수 있는 표준 도구 세트 제공

---

## 🚀 빠른 시작

```bat
# 1. 원클릭 실행
run.bat
```

브라우저에서 `http://localhost:8003` 접속.

---

## 🛠️ MCP 서버 연동 (Claude Desktop / Antigravity 설정)

`claude_desktop_config.json` 또는 에이전트 MCP 설정에 추가:

```json
{
  "mcpServers": {
    "blender_studio": {
      "command": "python",
      "args": ["D:/Project_Act/4.Contents_Post_Media_Build-CLAUDE/Contentsmaker-3-Blender/mcp_server.py"]
    }
  }
}
```

제공 도구:
- `get_blender_status`: Blender 설치 상태 및 GPU 가속 감지
- `render_3d_shot`: 3D 빌딩, 조명(선셋/네온), 캐릭터, 카메라 샷 파라미터 기반 렌더링
- `list_rendered_clips`: 렌더링된 MP4 클립/썸네일 목록 확인
- `send_to_contentsmaker2`: 4-2 씬 카드로 직행 주입
