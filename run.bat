@echo off
chcp 65001 > nul
title Contentsmaker-3-Blender Studio (Port 8003)

cd /d "%~dp0"

echo ========================================================
echo   [Contentsmaker-3-Blender Studio] 3D Local Studio
echo   - Local RTX GPU Rendering ($0 Cost)
echo   - Blender MCP Integration
echo   - Direct Drop & Bridge to Contentsmaker-2 (4-2)
echo ========================================================
echo.

if not exist ".venv" (
    echo [1/3] 가상환경(.venv) 생성 중...
    python -m venv .venv
)

echo [2/3] 의존성 패키지 확인 및 설치 중...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo [3/3] Contentsmaker-3-Blender 서버 시작 (포트 8003)...
start http://localhost:8003
python server.py

pause
