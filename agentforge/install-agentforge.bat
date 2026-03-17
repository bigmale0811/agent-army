@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================================
::  AgentForge 一鍵安裝包 v2
:: ============================================================

echo.
echo  ============================================
echo.
echo     AgentForge 一鍵安裝精靈
echo     只要等它跑完就好，不用做任何事
echo.
echo  ============================================
echo.

:: ----------------------------------------------------------
::  第零步：安裝位置 = bat 檔所在的資料夾
:: ----------------------------------------------------------
cd /d "%~dp0"
set "INSTALL_DIR=%CD%\my-agentforge"
echo  安裝位置: %INSTALL_DIR%
echo.

:: ----------------------------------------------------------
::  第一步：檢查 Python
:: ----------------------------------------------------------
echo  [1/4] 檢查你的電腦有沒有 Python...
echo.

where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    echo        已找到 !PYVER!
    echo.
    set PYTHON_CMD=python
    goto :step3
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('py --version 2^>^&1') do set PYVER=%%v
    echo        已找到 !PYVER!
    echo.
    set PYTHON_CMD=py
    goto :step3
)

echo        沒有找到 Python，現在幫你安裝...
echo.

:: ----------------------------------------------------------
::  第二步：自動下載並安裝 Python
:: ----------------------------------------------------------
echo  [2/4] 正在下載 Python 安裝檔...
echo        (大約 25MB，需要 1-3 分鐘)
echo.

set PYTHON_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe
set PYTHON_INSTALLER=%TEMP%\python-installer.exe

powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%' -UseBasicParsing" 2>nul

if not exist "%PYTHON_INSTALLER%" (
    echo.
    echo  !! 下載失敗！請檢查網路連線後再試一次。
    echo.
    pause
    exit /b 1
)

echo        下載完成！正在安裝 Python...
echo        (會出現安裝視窗，等它跑完就好)
echo.

"%PYTHON_INSTALLER%" /passive PrependPath=1 Include_pip=1 Include_test=0

if %errorlevel% neq 0 (
    echo.
    echo        安裝失敗。請對這個檔案按右鍵
    echo        選「以系統管理員身分執行」再試一次。
    echo.
    pause
    exit /b 1
)

del "%PYTHON_INSTALLER%" >nul 2>&1
echo        Python 安裝完成！
echo.

:: 重新載入 PATH
set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
set PYTHON_CMD=python

:: ----------------------------------------------------------
::  第三步：安裝 AgentForge
:: ----------------------------------------------------------
:step3
echo  [3/4] 正在安裝 AgentForge...
echo        (大約需要 2-3 分鐘，請耐心等候)
echo.

:: 先移除可能存在的 PyPI 同名假套件
%PYTHON_CMD% -m pip uninstall agentforge -y >nul 2>&1
%PYTHON_CMD% -m pip install --upgrade pip >nul 2>&1

:: 從 GitHub 安裝真正的 AgentForge
echo        正在從網路下載 AgentForge...
%PYTHON_CMD% -m pip install "agentforge @ https://github.com/bigmale0811/agent-army/archive/refs/heads/master.zip#subdirectory=agentforge"

if %errorlevel% neq 0 (
    echo.
    echo  !! AgentForge 安裝失敗。
    echo     可能的原因:
    echo     1. 網路連線不穩定，請重試
    echo     2. 需要系統管理員權限
    echo.
    pause
    exit /b 1
)

:: 驗證安裝成功
%PYTHON_CMD% -m agentforge --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  !! AgentForge 安裝可能不完整，請重試。
    echo.
    pause
    exit /b 1
)

echo.
echo        AgentForge 安裝成功!
echo.

:: ----------------------------------------------------------
::  第四步：檢查 Node.js（Claude Code CLI 需要）
:: ----------------------------------------------------------
echo  [4/5] 檢查 Node.js（部分 AI 服務需要）...
echo.

where node >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do set NODEVER=%%v
    echo        已找到 Node.js !NODEVER!
    echo.
    goto :step5
)

echo        沒有找到 Node.js。
echo        如果你想用 Claude Code（選項 2），需要 Node.js。
echo        如果你選 Gemini（選項 1），可以跳過。
echo.
echo        要自動安裝 Node.js 嗎？
echo        1. 是，幫我安裝（建議）
echo        2. 不用，我用 Gemini 就好
echo.

set NODE_CHOICE=1
set /p NODE_CHOICE="你的選擇（預設 1）: "

if "!NODE_CHOICE!"=="2" (
    echo        已跳過 Node.js 安裝。
    echo.
    goto :step5
)

echo        正在下載 Node.js 安裝檔...
echo        (大約 30MB，需要 1-3 分鐘)
echo.

set NODE_URL=https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi
set NODE_INSTALLER=%TEMP%\node-installer.msi

powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%NODE_INSTALLER%' -UseBasicParsing" 2>nul

if not exist "%NODE_INSTALLER%" (
    echo.
    echo  !! Node.js 下載失敗，但不影響安裝。
    echo     如果之後要用 Claude，可以手動安裝：https://nodejs.org
    echo.
    goto :step5
)

echo        下載完成！正在安裝 Node.js...
echo        (會出現安裝視窗，等它跑完就好)
echo.

msiexec /i "%NODE_INSTALLER%" /passive /norestart

del "%NODE_INSTALLER%" >nul 2>&1

:: 重新載入 PATH（Node.js 預設安裝路徑）
set "PATH=%ProgramFiles%\nodejs;%PATH%"

where node >nul 2>&1
if %errorlevel% equ 0 (
    echo        Node.js 安裝成功！
) else (
    echo        Node.js 安裝完成，可能需要重啟終端機才能生效。
)
echo.

:: ----------------------------------------------------------
::  第五步：建立專案並啟動安裝精靈
:: ----------------------------------------------------------
:step5
echo  [5/5] 建立專案並啟動安裝精靈...
echo.

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"

%PYTHON_CMD% -m agentforge init . 2>&1

echo.
echo  ============================================
echo   接下來精靈會用中文問你幾個問題，
echo   照著回答就好!
echo.
echo   如果你有 Claude Pro/Max 訂閱，選 2
echo   如果沒有，選 1（Gemini 免費）
echo  ============================================
echo.

%PYTHON_CMD% -m agentforge setup

echo.
echo  ============================================
echo.
echo     安裝全部完成!
echo.
echo     你的 AgentForge 在這裡:
echo     %INSTALL_DIR%
echo.
echo     想試跑 AI，輸入:
echo     %PYTHON_CMD% -m agentforge run example
echo.
echo  ============================================
echo.

cmd /k
