# Contentsmaker-3-Blender (4-3)

> **편당 0원** — 내 컴퓨터의 RTX GPU 로 블렌더가 3D 장면을 렌더합니다. 유료 AI 영상·이미지 API 는 **한 줄도 부르지 않습니다.**
> 4-3 이 만드는 것은 **장면 클립(MP4) + 썸네일(PNG)** 뿐이고, 나레이션·자막·음악·유튜브 업로드는 **4-2(TubeInsight)** 가 합니다.

---

## ⚡ 한 장 요약

| | |
|---|---|
| 하는 일 | 3D 건물·조명·카메라 무빙을 정해 **MP4 클립과 썸네일 PNG** 를 렌더 |
| 비용 | **0원** (로컬 블렌더). 유료 AI 호출 코드 없음 — `requirements.txt` 에 AI SDK 가 없습니다 |
| 포트 | **8003** (`config.json` 의 `port` 또는 환경변수 `PORT` 로 변경) |
| 4-2 주소 | **http://localhost:4005** (`config.json` 의 `cm2_url` 또는 환경변수 `CM2_URL`) |
| 4-2 와의 접점 | **입구 하나** — 4-2 의 `/api/render/media`. 4-2 폴더에 파일을 직접 만들지 않습니다 |
| 결과물 자리 | `outputs/` (렌더 결과) · `temp/` (블렌더에 넘기는 임시 스크립트). **이 두 곳 밖에는 쓰지 않습니다** |

---

## 🚀 켜는 법

```bat
run.bat
```

브라우저에서 `http://localhost:8003` 이 열립니다.

- **포트 8003 이 이미 쓰이고 있으면** 4-3 은 **그 서버를 끄지 않고 멈춥니다.** 다른 포트로 켜려면:
  ```bat
  set PORT=8013 && python server.py
  ```
- **블렌더가 없으면** 화면이 죽지 않고 「블렌더를 찾을 수 없습니다」와 **찾아본 자리 목록**을 보여 줍니다.
  화면의 경로 지정 칸에 `blender.exe` 위치를 넣거나, 환경변수 `BLENDER_PATH` 를 쓰십시오.

### 확인된 환경 (2026-10-27)

- 블렌더 **4.5.10 LTS** — `C:\Program Files\Blender Foundation\Blender 4.5\blender.exe`
- GPU 가속 **OPTIX / NVIDIA GeForce RTX 3060** (블렌더에게 직접 물어서 확인합니다 — 모르면 `null`, 지어내지 않습니다)

---

## 🔗 4-2 로 보내기 (직송)

4-2 를 먼저 켜 두십시오 (4-2 폴더의 `run.bat`, 주소 `http://localhost:4005`).

1. 4-3 화면에서 클립의 **🚀 버튼**을 누릅니다.
2. **기획안 ID(plan_id)** 와 **씬 슬롯**을 고릅니다.
3. 주입하면 4-2 의 그 씬 카드에 바로 붙습니다.

### 슬롯 표기 — 여기가 중요합니다

4-2 는 **씬 번호(`1`, `2`, `3` …)** 와 **`thumbnail`** 만 알아봅니다. `scene_1` 같은 표기는 **받지 않습니다.**
4-3 은 4-2 를 부르기 전에 슬롯을 검사해, 엉뚱한 값이면 보내지 않고 한국말로 거절합니다.

| 슬롯 | 보내는 파일 |
|---|---|
| `1`, `2`, `3` … | `outputs/<작업ID>.mp4` (영상) |
| `thumbnail` | `outputs/<작업ID>_thumb.png` (이미지) — 썸네일 칸에 영상은 들어가지 않습니다 |

4-2 가 꺼져 있으면 「4-2(http://localhost:4005)가 꺼져 있습니다 — 4-2 폴더의 run.bat 으로 켜신 뒤 다시 보내 주십시오」로 알립니다.

---

## 🛠️ MCP 서버 연동 (Claude Desktop / Antigravity)

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
- `get_blender_status`: 블렌더 설치 상태·버전·GPU 가속 여부
- `render_3d_shot`: 3D 빌딩·조명·카메라 샷 설정으로 렌더
- `list_rendered_clips`: 렌더된 클립 목록
- `send_to_contentsmaker2`: 4-2 씬 카드로 직송 (`slot` 은 `'1'`, `'2'`, `'thumbnail'`)

---

## ⚙️ 설정 (`config.json`)

주소·포트를 코드에 박지 않습니다. **환경변수 > `config.json` > 기본값** 순서로 읽습니다.

```json
{
  "cm2_url": "http://localhost:4005",
  "port": 8003,
  "storage_warn_clips": 40,
  "storage_warn_mb": 2048
}
```

| 값 | 환경변수 | 기본값 | 뜻 |
|---|---|---|---|
| `cm2_url` | `CM2_URL` | `http://localhost:4005` | 4-2 주소 |
| `port` | `PORT` | `8003` | 4-3 포트 |
| `storage_warn_clips` / `storage_warn_mb` | `STORAGE_WARN_CLIPS` / `STORAGE_WARN_MB` | 40개 / 2048MB | 보관 알림 기준 |
| (없음) | `BLENDER_PATH` | 자동 탐색 | `blender.exe` 경로 |
| `blender_path` | — | 자동 탐색 | 화면에서 지정하면 여기에 저장됩니다 |

**보관 한도는 알림까지만 합니다. 4-3 은 렌더 결과를 자동으로 지우지 않습니다.** 기준을 넘으면 화면 위에 알림이 뜨니, 필요 없는 것은 직접 지우십시오.

---

## 📋 현황 쪽지 — `report/report.json`

98번(관제탑) 공통 규격(`docs/briefs/00-report-contract.md`)에 맞춰 자기 상태를 적습니다. 서버가 켜질 때·상태를 물을 때·렌더가 끝날 때 다시 씁니다.

`state` 정하는 규칙:
1. **`down`** — 블렌더를 찾을 수 없다 (렌더라는 핵심 일을 못 한다).
2. **`degraded`** — 렌더 실패가 있거나 `outputs` 보관 기준을 넘었다 (알림이 하나라도 있다).
3. **`ok`** — 위에 해당 없음. 서버를 끄면 마지막으로 **`idle`** 을 적습니다 (손으로 켜는 도구라 `heartbeatHours` 는 `null`).

AI 비용 칸은 언제나 **0원**입니다 (`usesAi: false`).

---

## 🧪 자가 시험

```bat
run_tests.bat
```
또는
```bat
python -m unittest discover -s tests -v
```

**돈 드는 호출도, 외부 발송도 하지 않습니다.** `tests/fake_cm2.py` 가 4-2 의 입구를 흉내 내는 **가짜 4-2 서버**라서, 진짜 4-2 를 켜지 않고도 직송 길(슬롯 규칙 · 썸네일 · 꺼져 있을 때 안내)을 시험합니다.

---

## 🚫 4-3 이 하지 않는 일

- 나레이션(TTS)·자막·음악·유튜브 업로드 — **4-2 가 합니다.**
- 유료 AI 영상·이미지 생성 API 호출 — **없습니다** (존재 이유가 편당 0원입니다).
- 4-2 폴더 파일 직접 쓰기 — 넣는 길은 4-2 입구 `/api/render/media` 하나뿐입니다.
- 포트가 겹칠 때 남의 서버 끄기 — 멈추고 알립니다.
- 렌더 결과 자동 삭제 — 알리기만 합니다.
