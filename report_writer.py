"""98번 공통 규격(docs/briefs/00-report-contract.md) 에 맞춘 현황 쪽지 쓰기.

- 자리: report/report.json (다 쓰고 나서 이름 바꾸기로 바꿔치기)
- 모르는 값은 null 로 둔다. 지어내지 않는다.
- 4-3 은 로컬 렌더만 하므로 AI 비용은 0원이다.
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

import config

BASE_DIR = Path(__file__).parent
REPORT_DIR = BASE_DIR / "report"
REPORT_FILE = REPORT_DIR / "report.json"
KST = timezone(timedelta(hours=9))

PROJECT = {"no": "4-3", "name": "Contentsmaker-3-Blender"}


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _recent_jobs(bridge, limit: int = 3) -> List[Dict[str, Any]]:
    jobs = []
    for meta in bridge.list_renders()[:limit]:
        jobs.append({
            "jobId": meta.get("job_id"),
            "status": meta.get("status"),
            "seconds": meta.get("seconds"),
            "file": meta.get("mp4_file"),
            "at": meta.get("created_at"),
        })
    return jobs


def build_report(bridge, state: Optional[str] = None, last_error: Optional[str] = None,
                 extra_alerts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    renders = bridge.list_renders()
    completed = len([m for m in renders if m.get("status") == "completed"])
    failed = len([m for m in renders if m.get("status") == "failed"])
    storage = bridge.storage_status()

    info = {}
    try:
        from blender_detector import get_blender_info
        info = get_blender_info(probe_gpu=True)  # 한 프로세스에 한 번만 실제로 물어본다 (뒤에는 기억해 둔 값)
    except Exception:
        info = {}

    alerts: List[Dict[str, Any]] = []
    error = last_error

    if not info.get("installed"):
        alerts.append({
            "level": "alert",
            "code": "blender-not-found",
            "text": "블렌더를 찾을 수 없어 렌더할 수 없습니다 (화면에서 blender.exe 경로를 지정해 주십시오)",
            "since": None,
        })
        if error is None:
            error = "블렌더를 찾을 수 없습니다."

    if failed:
        last_failed = next((m for m in renders if m.get("status") == "failed"), None)
        alerts.append({
            "level": "warn",
            "code": "render-failed",
            "text": f"렌더 실패 {failed}건 (가장 최근: {last_failed.get('job_id') if last_failed else '?'})"[:120],
            "since": None,
        })
        if error is None and last_failed:
            error = str(last_failed.get("error") or "렌더 실패")[:200]

    if storage.get("over_limit"):
        alerts.append({
            "level": "warn",
            "code": "outputs-piling-up",
            "text": f"outputs 에 클립 {storage['clips']}개 · {storage['megabytes']}MB (자동 삭제하지 않음)"[:120],
            "since": None,
        })

    if state is None:
        if not info.get("installed"):
            state = "down"
        elif alerts:
            state = "degraded"
        else:
            state = "ok"

    gpu = (info.get("gpu") or {})
    headline = (
        f"렌더 {completed}편 완료 · 실패 {failed} · 보관 {storage['clips']}편 "
        f"({'GPU' if gpu.get('accelerated') else 'GPU 미확인' if gpu.get('accelerated') is None else 'CPU'})"
    )[:60]

    return {
        "schemaVersion": 1,
        "project": PROJECT,
        "generatedAt": _now(),
        "state": state,
        "headline": headline,
        "lastError": error,
        "alerts": (alerts + (extra_alerts or []))[:5],
        "counts": {
            "rendersCompleted": completed,
            "rendersFailed": failed,
            "clipsStored": storage["clips"],
            "outputsMegabytes": storage["megabytes"],
        },
        "usesAi": False,
        "spend": {
            "month": time.strftime("%Y-%m"),
            "monthKrw": 0,
            "basis": "measured",
            "byProvider": {},
        },
        "top": [
            {"title": f"{j['jobId']} · {j['status']}", "url": None, "at": j["at"]}
            for j in _recent_jobs(bridge)
        ],
        "heartbeatHours": None,
        # ── 4-3 고유 칸 ───────────────────────────────────────────────
        "blender": {
            "installed": info.get("installed"),
            "version": info.get("version"),
            "path": info.get("path"),
            "gpuAccelerated": gpu.get("accelerated"),
            "gpuBackend": gpu.get("backend"),
        },
        "recentJobs": _recent_jobs(bridge),
        "storage": storage,
        "cm2Url": config.get_cm2_url(),
    }


def write_report(bridge, **kwargs) -> Dict[str, Any]:
    report = build_report(bridge, **kwargs)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REPORT_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    os.replace(tmp, REPORT_FILE)
    return report


if __name__ == "__main__":
    from blender_bridge import bridge
    print(json.dumps(write_report(bridge), indent=2, ensure_ascii=False))
