@echo off
:: stop_proxy.bat - 프록시 서버 종료
echo 프록시(Node) 프로세스를 종료합니다...

:: 1) 포트 3000을 사용하는 PID 찾기 (Windows 10+)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
  set PID=%%a
)

if "%PID%"=="" (
  echo 포트 3000에서 LISTENING 중인 프로세스를 찾지 못했습니다. (이미 종료되었을 수 있음)
  goto :eof
)

echo PID %PID% 종료 시도...
taskkill /PID %PID% /F >nul 2>&1
if errorlevel 1 (
  echo taskkill 실패. 관리자 권한으로 다시 시도하거나, 수동 종료하세요.
) else (
  echo 완료: PID %PID% 종료됨.
)