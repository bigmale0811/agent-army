@echo off
REM ============================================================
REM  日本博弈資訊蒐集 Agent — Windows Task Scheduler 設定腳本
REM  設定每週一早上 09:00 自動執行蒐集並發送報告
REM ============================================================

echo ====================================================
echo  日本博弈資訊蒐集 Agent - 排程設定工具
echo ====================================================
echo.

REM 設定變數
set TASK_NAME=JapanIntelWeeklyReport
set PROJECT_DIR=D:\Projects\agent-army
set PYTHON_PATH=python

REM 檢查是否以管理員身份執行
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 請以管理員身份執行此腳本！
    echo 右鍵點擊 -^> 以系統管理員身分執行
    pause
    exit /b 1
)

echo [1/3] 建立每週一 09:00 的排程工作...
echo.

REM 刪除舊的排程（如果存在）
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM 建立新排程：每週一 09:00
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON_PATH%\" -m src.japan_intel.runner --mode weekly" ^
    /sc weekly /d MON /st 09:00 ^
    /sd %date:~0,4%/%date:~5,2%/%date:~8,2% ^
    /rl HIGHEST ^
    /f

if %errorlevel% neq 0 (
    echo [錯誤] 排程建立失敗！
    pause
    exit /b 1
)

echo.
echo [2/3] 設定工作目錄...

REM 使用 PowerShell 設定工作目錄（schtasks 不直接支援）
powershell -Command ^
    "$action = New-ScheduledTaskAction -Execute '%PYTHON_PATH%' -Argument '-m src.japan_intel.runner --mode weekly' -WorkingDirectory '%PROJECT_DIR%'; $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am; Set-ScheduledTask -TaskName '%TASK_NAME%' -Action $action"

echo.
echo [3/3] 驗證排程設定...
echo.
schtasks /query /tn "%TASK_NAME%" /v /fo list

echo.
echo ====================================================
echo  排程設定完成！
echo  工作名稱: %TASK_NAME%
echo  執行時間: 每週一 09:00
echo  執行命令: python -m src.japan_intel.runner --mode weekly
echo  工作目錄: %PROJECT_DIR%
echo ====================================================
echo.
echo 如需手動測試，請執行：
echo   cd %PROJECT_DIR%
echo   python -m src.japan_intel.runner --mode weekly --dry-run
echo.
pause
