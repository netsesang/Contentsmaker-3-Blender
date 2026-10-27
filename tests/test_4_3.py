# -*- coding: utf-8 -*-
"""4-3 자가 시험. 돈이 드는 호출도, 외부 발송도 하지 않는다.

    python -m unittest discover -s tests -v      (또는 run_tests.bat)

여기서 시험하는 것:
  A1·A2  설정(4-2 주소 4005)과 환경변수 우선순위
  A3     슬롯 검사 (엉뚱한 값 · thumbnail + mp4 거절)
  A4(대역) 가짜 4-2 서버로 하는 직송 성공 — 진짜 4-2 직송은 사람이 한 번 더 한다
  A5     4-2 가 꺼져 있을 때 한국말 안내
  A6     블렌더가 없을 때 죽지 않고 찾아본 자리 알림
  B1     report.json 이 98번 규격을 지키는지
  B2     렌더 결과가 outputs/ · temp/ 밖으로 나가지 않는지 (경로 상수 확인)
  B3     보관 한도 알림 (자동 삭제 없음)
  C1     포트가 이미 쓰이면 멈추는 검사 함수
"""
import importlib
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import config                      # noqa: E402
import blender_bridge              # noqa: E402
import blender_detector            # noqa: E402
import report_writer               # noqa: E402
import fake_cm2                    # noqa: E402

bridge = blender_bridge.bridge


def _reload_config():
    importlib.reload(config)
    return config


class TestConfig(unittest.TestCase):
    """A1 · A2 — 주소를 코드에 박지 않는다. 기본값은 4005."""

    def tearDown(self):
        os.environ.pop("CM2_URL", None)
        os.environ.pop("PORT", None)

    def test_default_cm2_url_is_4005(self):
        self.assertEqual(config.get_cm2_url(), "http://localhost:4005")

    def test_env_overrides_config_file(self):
        os.environ["CM2_URL"] = "http://127.0.0.1:4999/"
        self.assertEqual(config.get_cm2_url(), "http://127.0.0.1:4999")

    def test_port_default_and_env(self):
        self.assertEqual(config.get_port(), 8003)
        os.environ["PORT"] = "8013"
        self.assertEqual(config.get_port(), 8013)

    def test_no_hardcoded_8002_left(self):
        for name in ("server.py", "blender_bridge.py", "mcp_server.py", "web/index.html", "web/app.js"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("8002", text, f"{name} 에 옛 주소 8002 가 남아 있습니다")
            self.assertNotIn("scene_1\"", text, f"{name} 에 옛 슬롯 표기 scene_1 이 남아 있습니다")


class TestSlotRules(unittest.TestCase):
    """A3 — 4-2 를 부르기 전에 슬롯을 검사한다."""

    def test_numbers_and_thumbnail_pass(self):
        for value, expected in (("1", "1"), (2, "2"), ("10", "10"), ("thumbnail", "thumbnail"), ("THUMBNAIL", "thumbnail")):
            slot, err = blender_bridge.normalize_slot(value)
            self.assertIsNone(err)
            self.assertEqual(slot, expected)

    def test_scene_1_is_rejected_with_hint(self):
        slot, err = blender_bridge.normalize_slot("scene_1")
        self.assertIsNone(slot)
        self.assertIn("'1'", err)

    def test_garbage_and_empty_rejected(self):
        for value in ("", None, "씬1", "0", "100", "thumb"):
            slot, err = blender_bridge.normalize_slot(value)
            self.assertIsNone(slot, f"{value!r} 은 거절되어야 합니다")
            self.assertTrue(err)

    def test_thumbnail_rejects_video(self):
        err = blender_bridge.check_slot_file("thumbnail", "shot_1.mp4")
        self.assertIsNotNone(err)
        self.assertIn("이미지", err)

    def test_thumbnail_accepts_png(self):
        self.assertIsNone(blender_bridge.check_slot_file("thumbnail", "shot_1_thumb.png"))

    def test_bad_slot_never_calls_cm2(self):
        # 주소를 일부러 아무도 없는 곳으로 둔다. 슬롯 검사에서 막히면 접속 자체를 하지 않는다.
        res = bridge.send_to_contentsmaker_2("shot_없음", "plan", "scene_2", cm2_url="http://127.0.0.1:1")
        self.assertFalse(res["success"])
        self.assertIn("슬롯", res["error"])


class TestSendToCm2(unittest.TestCase):
    """A4(대역) · A5 — 가짜 4-2 로 직송, 그리고 꺼져 있을 때."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.url, self.stop = fake_cm2.start(self.tmp.name)
        self.job_id = f"selftest_{os.getpid()}"
        self.mp4 = blender_bridge.OUTPUTS_DIR / f"{self.job_id}.mp4"
        self.png = blender_bridge.OUTPUTS_DIR / f"{self.job_id}_thumb.png"
        self.mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
        self.png.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    def tearDown(self):
        self.stop()
        self.tmp.cleanup()
        for f in (self.mp4, self.png):
            if f.exists():
                f.unlink()

    def test_send_video_to_scene_slot(self):
        res = bridge.send_to_contentsmaker_2(self.job_id, "plan_test", "2", cm2_url=self.url)
        self.assertTrue(res.get("success"), res.get("error"))
        self.assertEqual(res["slot"], "2")
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "scene_02.mp4")))

    def test_send_thumbnail_sends_png_not_mp4(self):
        res = bridge.send_to_contentsmaker_2(self.job_id, "plan_test", "thumbnail", cm2_url=self.url)
        self.assertTrue(res.get("success"), res.get("error"))
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "thumbnail.png")))

    def test_old_scene_1_would_have_failed_on_real_cm2(self):
        """98번이 적은 결함 2 재현 — 검사를 건너뛰고 'scene_1' 을 그대로 보내면 4-2 는 거절한다."""
        import base64
        import requests
        payload = {
            "plan_id": "plan_test",
            "slot": "scene_1",
            "filename": self.mp4.name,
            "data_base64": "data:video/mp4;base64," + base64.b64encode(self.mp4.read_bytes()).decode(),
        }
        resp = requests.post(f"{self.url}/api/render/media", json=payload, timeout=10)
        self.assertEqual(resp.status_code, 400)

    def test_missing_file_message(self):
        res = bridge.send_to_contentsmaker_2("shot_없는것", "plan_test", "1", cm2_url=self.url)
        self.assertFalse(res["success"])
        self.assertIn("보낼 파일이 없습니다", res["error"])

    def test_cm2_offline_message_is_korean(self):
        self.stop()  # 4-2 를 끈다
        res = bridge.send_to_contentsmaker_2(self.job_id, "plan_test", "1", cm2_url=self.url)
        self.assertFalse(res["success"])
        self.assertIn("꺼져 있습니다", res["error"])
        self.assertIn("run.bat", res["error"])
        self.assertNotIn("Traceback", res["error"])
        self.assertNotIn("ConnectionError", res["error"])


class TestBlenderMissing(unittest.TestCase):
    """A6 — 블렌더가 없어도 죽지 않고, 찾아본 자리를 알린다."""

    def setUp(self):
        self.saved = (blender_detector.DEFAULT_SEARCH_PATHS, os.environ.get("BLENDER_PATH"))
        blender_detector.DEFAULT_SEARCH_PATHS = [r"Z:\없는폴더\blender.exe"]
        os.environ["BLENDER_PATH"] = r"Z:\없는폴더\blender.exe"
        self._where = blender_detector.subprocess.run
        blender_detector.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(OSError("where.exe 없음"))

    def tearDown(self):
        blender_detector.DEFAULT_SEARCH_PATHS = self.saved[0]
        blender_detector.subprocess.run = self._where
        if self.saved[1] is None:
            os.environ.pop("BLENDER_PATH", None)
        else:
            os.environ["BLENDER_PATH"] = self.saved[1]

    def test_info_reports_searched_paths(self):
        info = blender_detector.get_blender_info()
        self.assertFalse(info["installed"])
        self.assertIsNone(info["gpu_detected"])          # 모르면 null — 지어내지 않는다
        self.assertIn("블렌더를 찾을 수 없습니다", info["message"])
        self.assertTrue(any("Z:" in p for p in info["searched_paths"]))

    def test_render_refuses_politely(self):
        res = bridge.start_render_job({"duration": 1.0})
        self.assertFalse(res["success"])
        self.assertIn("블렌더를 찾을 수 없습니다", res["error"])
        self.assertTrue(res["searched_paths"])


class TestReport(unittest.TestCase):
    """B1 — 98번 공통 규격(00-report-contract.md)."""

    def test_report_shape(self):
        report = report_writer.build_report(bridge)
        for key in ("schemaVersion", "project", "generatedAt", "state", "headline", "lastError", "alerts"):
            self.assertIn(key, report)
        self.assertEqual(report["schemaVersion"], 1)
        self.assertEqual(report["project"]["no"], "4-3")
        self.assertIn(report["state"], ("ok", "degraded", "down", "idle"))
        self.assertLessEqual(len(report["headline"]), 60)
        self.assertLessEqual(len(report["alerts"]), 5)
        for alert in report["alerts"]:
            self.assertIn(alert["level"], ("info", "warn", "alert"))
            self.assertLessEqual(len(alert["text"]), 120)
        self.assertIs(report["usesAi"], False)
        self.assertEqual(report["spend"]["monthKrw"], 0)        # 로컬 렌더 — 0원
        self.assertIsNone(report["heartbeatHours"])             # 손으로 켜는 도구
        json.dumps(report, ensure_ascii=False)                  # 직렬화 가능해야 한다

    def test_report_file_is_written_atomically(self):
        report_writer.write_report(bridge)
        self.assertTrue(report_writer.REPORT_FILE.exists())
        json.loads(report_writer.REPORT_FILE.read_text(encoding="utf-8"))
        self.assertFalse(report_writer.REPORT_FILE.with_suffix(".json.tmp").exists())


class TestStorageAndPaths(unittest.TestCase):
    """B2 · B3 — 쓰는 자리는 outputs/ 와 temp/ 뿐, 보관은 알림까지만."""

    def test_output_dirs(self):
        self.assertEqual(blender_bridge.OUTPUTS_DIR, ROOT / "outputs")
        self.assertEqual(blender_bridge.SCRIPTS_DIR, ROOT / "temp")
        source = (ROOT / "scene_generator.py").read_text(encoding="utf-8")
        self.assertNotIn("C:\\\\", source)   # 렌더 경로를 코드에 박지 않는다

    def test_storage_status_fields(self):
        status = bridge.storage_status()
        for key in ("clips", "megabytes", "limit_clips", "limit_megabytes", "over_limit", "warning"):
            self.assertIn(key, status)

    def test_storage_warning_triggers_without_deleting(self):
        before = sorted(os.listdir(blender_bridge.OUTPUTS_DIR))
        os.environ["STORAGE_WARN_CLIPS"] = "1"
        os.environ["STORAGE_WARN_MB"] = "1"
        try:
            status = bridge.storage_status()
            self.assertTrue(status["over_limit"])
            self.assertIn("자동으로 지우지 않습니다", status["warning"])
        finally:
            os.environ.pop("STORAGE_WARN_CLIPS", None)
            os.environ.pop("STORAGE_WARN_MB", None)
        self.assertEqual(before, sorted(os.listdir(blender_bridge.OUTPUTS_DIR)))  # 아무것도 지우지 않았다


class TestPortGuard(unittest.TestCase):
    """C1 — 포트가 이미 쓰이면 멈춘다 (남의 서버는 끄지 않는다)."""

    def test_detects_busy_and_free_port(self):
        import server
        busy = socket.socket()
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        try:
            self.assertTrue(server.port_in_use(port))
        finally:
            busy.close()
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        free_port = free.getsockname()[1]
        free.close()
        self.assertFalse(server.port_in_use(free_port))


if __name__ == "__main__":
    unittest.main(verbosity=2)
