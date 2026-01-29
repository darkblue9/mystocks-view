@echo off
setlocal ENABLEDELAYEDEXPANSION

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js 가 설치되어 있지 않습니다.
  echo https://nodejs.org/ko/download 에서 LTS 버전 설치 후 다시 실행하세요.
  pause
  exit /b 1
)

if not exist "finnhub-proxy.js" (
  echo [ERROR] finnhub-proxy.js 파일을 이 배치파일과 같은 폴더에 두세요.
  pause
  exit /b 1
)

if "%FINNHUB_API_KEY%"=="" (
  set /p FINNHUB_API_KEY=FINNHUB_API_KEY 를 입력하세요 (finnhub.io 에서 발급): 
  if "%FINNHUB_API_KEY%"=="" (
    echo [ERROR] API 키가 필요합니다.
    pause
    exit /b 1
  )
)

if not exist "package.json" (
  echo npm init -y
  call npm init -y
)
call npm install express node-fetch@2 cors

echo.
echo [INFO] 프록시를 시작합니다: http://localhost:3000
echo [TIP ] 이 창은 켜두고, 브라우저에서 index_compact_debug.html 을 열어 사용하세요.
echo.

set PORT=3000
node finnhub-proxy.js
