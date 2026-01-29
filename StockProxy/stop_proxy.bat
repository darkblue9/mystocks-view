@echo off
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do set PID=%%a
if "%PID%"=="" ( echo 포트 3000 LISTENING 없음 ) else ( taskkill /PID %PID% /F )
