@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Banana 英文字母麻將

set "PORT=8000"

echo.
echo   ====================================
echo    BANANA 英文字母麻將
echo   ====================================
echo.

rem ---------------- 檢查環境 ----------------
where python >nul 2>nul
if errorlevel 1 goto no_python

where bun >nul 2>nul
if errorlevel 1 goto no_bun

rem ---------------- 首次安裝 ----------------
if exist "server\.venv\Scripts\python.exe" goto venv_ok
echo   [1/3] 第一次執行，建立 Python 環境（只會做一次）...
python -m venv "server\.venv"
if errorlevel 1 goto venv_fail
rem 有些 Windows 的 Python 建出來的 venv 不含 pip，補一次
"server\.venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 "server\.venv\Scripts\python.exe" -m ensurepip --upgrade
"server\.venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 goto pip_fail
"server\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
"server\.venv\Scripts\python.exe" -m pip install --quiet fastapi "uvicorn[standard]" pydantic websockets
if errorlevel 1 goto venv_fail
goto venv_done
:venv_ok
echo   [1/3] Python 環境 OK
:venv_done

if exist "web\node_modules" goto node_ok
echo   [2/3] 安裝前端套件（第一次會久一點）...
pushd web
call bun install
popd
goto node_done
:node_ok
echo   [2/3] 前端套件 OK
:node_done

echo   [3/3] 打包前端...
pushd web
call bun run build
if errorlevel 1 goto build_fail
popd

rem ---------------- 選擇連線方式 ----------------
echo.
echo   要怎麼開？
echo.
echo     [1] 本機 + 同區網的朋友
echo     [2] Tailscale Funnel（公開網址，朋友什麼都不用裝）
echo.
set "MODE="
set /p "MODE=   輸入 1 或 2 然後按 Enter > "
if "%MODE%"=="2" goto funnel

:lan
set "BIND=0.0.0.0"
echo.
echo   你自己開：  http://localhost:%PORT%
echo.
echo   區網的朋友開：
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  set "ip=%%a"
  set "ip=!ip: =!"
  echo                http://!ip!:%PORT%
)
echo.
echo   （第一次可能會跳防火牆提示，要按「允許存取」）
goto run

:funnel
set "BIND=127.0.0.1"
set "TS=tailscale"
where tailscale >nul 2>nul
if not errorlevel 1 goto ts_found
set "TS=C:\Program Files\Tailscale\tailscale.exe"
if not exist "%TS%" goto no_tailscale
:ts_found
echo.
echo   啟動 Tailscale Funnel...
"%TS%" funnel --bg %PORT%
if errorlevel 1 goto funnel_fail
"%TS%" funnel status
set "FUNNEL=1"
echo.
echo   上面那個 https://....ts.net 的網址就是給朋友的
echo   注意：那是公開網址，玩完這個視窗關掉就會自動收起來
goto run

rem ---------------- 啟動 ----------------
:run
rem ---- 檢查連接埠有沒有被上一次沒關乾淨的 server 佔住 ----
set "BUSY="
for /f "tokens=5" %%p in ('netstat -aon ^| findstr /c:":%PORT% " ^| findstr /c:"LISTENING"') do set "BUSY=%%p"
if not defined BUSY goto port_ok
echo.
echo   連接埠 %PORT% 已被 PID %BUSY% 佔用（多半是上一次沒關乾淨的伺服器）：
tasklist /fi "pid eq %BUSY%" /fo table /nh
set "KILL="
set /p "KILL=   要結束它嗎？(y/n) > "
if /i not "%KILL%"=="y" goto bye
taskkill /f /pid %BUSY% >nul 2>nul
timeout /t 1 /nobreak >nul
:port_ok

"server\.venv\Scripts\python.exe" -c "import uvicorn" 2>nul
if errorlevel 1 (
  echo   套件不完整，重新安裝...
  "server\.venv\Scripts\python.exe" -m ensurepip --upgrade >nul 2>nul
  "server\.venv\Scripts\python.exe" -m pip install --quiet fastapi "uvicorn[standard]" pydantic websockets
)
set "BANANA_WEB_DIST=%CD%\web\dist"
start "" /min cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:%PORT%"
echo.
echo   ------------------------------------
echo    伺服器啟動中，瀏覽器會自動打開
echo    要停止：按 Ctrl+C 或直接關掉這個視窗
echo   ------------------------------------
echo.
"server\.venv\Scripts\python.exe" -m uvicorn banana.app:app --host %BIND% --port %PORT% --app-dir server

if not defined FUNNEL goto bye
echo.
echo   收起 Tailscale Funnel...
"%TS%" funnel --https=443 off >nul 2>nul
"%TS%" funnel status
goto bye

rem ---------------- 錯誤處理 ----------------
:no_python
echo   [錯誤] 找不到 python
echo.
echo   請安裝 Python 3.11 以上：https://www.python.org/downloads/
echo   安裝時記得勾「Add python.exe to PATH」，裝完重開這個檔案
goto bye

:no_bun
echo   [錯誤] 找不到 bun
echo.
echo   請在 PowerShell 執行：
echo       powershell -c "irm bun.sh/install.ps1^|iex"
echo   裝完「重開終端機」，再重開這個檔案
goto bye

:no_tailscale
echo   [錯誤] 找不到 tailscale
echo.
echo   請先安裝並登入 Tailscale：https://tailscale.com/download/windows
goto bye

:pip_fail
echo.
echo   [錯誤] 這個 venv 裡沒有 pip，也補不回來
echo   請手動刪掉 server\.venv 資料夾後重開這個檔案；
echo   還是不行的話，重裝一次 Python（官方安裝包，不要用 Microsoft Store 版）
goto bye

:venv_fail
echo.
echo   [錯誤] Python 環境建立失敗，把上面的訊息截圖下來問人
goto bye

:build_fail
popd
echo.
echo   [錯誤] 前端打包失敗，試著手動跑一次看錯在哪：
echo       cd web
echo       bun run build
goto bye

:funnel_fail
echo.
echo   [錯誤] Funnel 啟動失敗
echo   第一次用要先在 Tailscale 後台開通 MagicDNS / HTTPS / funnel 屬性，
echo   上面的訊息裡通常會直接給你開通的連結。
goto bye

:bye
echo.
pause
endlocal
