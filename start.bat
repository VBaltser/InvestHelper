@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "UVICORN=%BACKEND%\.venv\Scripts\uvicorn.exe"
set "URL=http://localhost:5173"

if not exist "%UVICORN%" (
  echo [InvestHelper] Не найден backend\.venv
  echo Создайте окружение: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist "%FRONTEND%\node_modules\" (
  echo [InvestHelper] Не найден frontend\node_modules
  echo Установите зависимости: cd frontend ^&^& npm install
  pause
  exit /b 1
)

echo [InvestHelper] Запуск backend на http://127.0.0.1:8000 ...
start "InvestHelper Backend" /D "%BACKEND%" cmd /k ""%UVICORN%" app.main:app --reload --port 8000"

echo [InvestHelper] Запуск frontend на %URL% ...
start "InvestHelper Frontend" /D "%FRONTEND%" cmd /k "npm run dev"

echo [InvestHelper] Ожидание готовности frontend...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url='%URL%'; $ok=$false; for($i=0;$i -lt 45;$i++){ try { $r=Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -ge 200){ $ok=$true; break } } catch {} Start-Sleep -Seconds 1 }; if(-not $ok){ Write-Host '[InvestHelper] Frontend ещё не ответил — открываю браузер всё равно.' }; Start-Process $url"

echo [InvestHelper] Готово. Окна Backend и Frontend можно закрыть, когда закончите работу.
endlocal
