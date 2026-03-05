@echo off
REM ============================================
REM 讀書 Agent v2 — 每週自動蒐集排程腳本
REM 每週日 21:00 由 Windows Task Scheduler 執行
REM ============================================

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

cd /d D:\Projects\agent-army

"C:\Users\goldbricks\AppData\Local\pypoetry\Cache\virtualenvs\claude-code-telegram-ZIo4rHZm-py3.12\Scripts\python.exe" -m src.reading_agent --mode weekly

if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] 讀書 Agent 每週蒐集失敗，錯誤碼: %ERRORLEVEL% >> D:\Projects\agent-army\logs\weekly_collect.log
) else (
    echo [%date% %time%] 讀書 Agent 每週蒐集完成 >> D:\Projects\agent-army\logs\weekly_collect.log
)
