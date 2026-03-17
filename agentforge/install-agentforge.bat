@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================================
::  AgentForge 一鍵安裝包
::  雙擊這個檔案，就能自動完成所有安裝步驟
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
::  第一步：檢查 Python 有沒有裝
:: ----------------------------------------------------------
echo  [1/4] 檢查你的電腦有沒有 Python...
echo.

python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    echo        已找到 !PYVER!
    echo.
    goto :install_agentforge
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('py --version 2^>^&1') do set PYVER=%%v
    echo        已找到 !PYVER!
    echo.
    goto :install_agentforge_py
)

echo        沒有找到 Python，現在幫你安裝...
echo.

:: ----------------------------------------------------------
::  第二步：自動下載並安裝 Python
:: ----------------------------------------------------------
echo  [2/4] 正在下載 Python 安裝檔，請稍等...
echo        (檔案大約 25MB，視網路速度需要 1-3 分鐘)
echo.

set PYTHON_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe
set PYTHON_INSTALLER=%TEMP%\python-installer.exe

powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%' -UseBasicParsing }" 2>nul

if not exist "%PYTHON_INSTALLER%" (
    echo.
    echo  !! 下載失敗！請檢查網路連線後再試一次。
    echo.
    echo  或者手動安裝 Python：
    echo  1. 打開 https://www.python.org
    echo  2. 點 Downloads 下載
    echo  3. 安裝時記得勾選 Add to PATH
    echo  4. 裝完後再雙擊這個檔案
    echo.
    pause
    exit /b 1
)

echo        下載完成！正在安裝 Python...
echo        (會出現安裝視窗，等它跑完就好)
echo.

:: /passive = 顯示進度條但不需要點按鈕
:: PrependPath=1 = 自動加入 PATH
:: Include_pip=1 = 包含 pip
"%PYTHON_INSTALLER%" /passive PrependPath=1 Include_pip=1 Include_test=0

if %errorlevel% neq 0 (
    echo.
    echo        安裝失敗。可能需要系統管理員權限。
    echo        請對這個檔案按右鍵 --^> 以系統管理員身分執行
    echo.
    pause
    exit /b 1
)

:: 清理安裝檔
del "%PYTHON_INSTALLER%" >nul 2>&1

echo        Python 安裝完成！
echo.

:: 重新載入 PATH（因為剛裝完 Python，舊的 CMD 視窗還不認識它）
set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"

:: 再次確認 Python 可用
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo        需要重新開啟視窗才能使用 Python。
    echo        請關閉這個視窗，然後再雙擊這個檔案一次。
    echo.
    pause
    exit /b 1
)

:: ----------------------------------------------------------
::  第三步：安裝 AgentForge（從 GitHub 安裝，不是 PyPI）
:: ----------------------------------------------------------
:install_agentforge
echo  [3/4] 正在安裝 AgentForge...
echo        (大約需要 1-2 分鐘)
echo.

:: 先移除 PyPI 上的同名假套件（如果有的話）
python -m pip uninstall agentforge -y >nul 2>&1
python -m pip install --upgrade pip >nul 2>&1

:: 從 GitHub 安裝我們真正的 AgentForge
python -m pip install "agentforge @ https://github.com/bigmale0811/agent-army/archive/refs/heads/master.zip#subdirectory=agentforge" 2>&1

if %errorlevel% neq 0 (
    echo.
    echo  !! 安裝失敗，請確認網路連線正常後再試一次。
    echo.
    pause
    exit /b 1
)

echo.
echo        AgentForge 安裝完成！
echo.

goto :run_setup

:install_agentforge_py
echo  [3/4] 正在安裝 AgentForge...
echo        (大約需要 1-2 分鐘)
echo.

:: 先移除 PyPI 上的同名假套件（如果有的話）
py -m pip uninstall agentforge -y >nul 2>&1
py -m pip install --upgrade pip >nul 2>&1

:: 從 GitHub 安裝我們真正的 AgentForge
py -m pip install "agentforge @ https://github.com/bigmale0811/agent-army/archive/refs/heads/master.zip#subdirectory=agentforge" 2>&1

if %errorlevel% neq 0 (
    echo.
    echo  !! 安裝失敗，請確認網路連線正常後再試一次。
    echo.
    pause
    exit /b 1
)

echo.
echo        AgentForge 安裝完成！
echo.

:: ----------------------------------------------------------
::  第四步：啟動安裝精靈
:: ----------------------------------------------------------
:run_setup
echo  [4/4] 啟動安裝精靈...
echo.
echo  ============================================
echo   接下來精靈會用中文問你幾個問題，
echo   照著回答就好！
echo  ============================================
echo.

:: 建立工作目錄在桌面
set DESKTOP=%USERPROFILE%\Desktop
set PROJECT_DIR=%DESKTOP%\my-agentforge

if not exist "%PROJECT_DIR%" (
    mkdir "%PROJECT_DIR%"
)
cd /d "%PROJECT_DIR%"

:: 先 init 專案，再跑 setup
agentforge init . >nul 2>&1
agentforge setup

echo.
echo  ============================================
echo.
echo     安裝全部完成！
echo.
echo     你的 AgentForge 已經裝好在桌面的
echo     「my-agentforge」資料夾裡
echo.
echo     想試跑 AI，在這個視窗輸入：
echo     agentforge run example
echo.
echo  ============================================
echo.

cmd /k
