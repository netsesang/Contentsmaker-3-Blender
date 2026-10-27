@echo off
chcp 65001 > nul
title Contentsmaker-3-Blender 자가 시험

cd /d "%~dp0"

echo ========================================================
echo   [4-3] 자가 시험 - 돈 드는 호출도 외부 발송도 없습니다
echo   가짜 4-2 서버로 직송 길까지 시험합니다.
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% -m unittest discover -s tests -v

echo.
pause
