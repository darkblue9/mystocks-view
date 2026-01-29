@echo off
setlocal EnableDelayedExpansion
where node >nul 2>&1 || (echo [ERROR] node not found & pause & exit /b 1)
if not exist "naver-proxy.js" (echo [ERROR] naver-proxy.js missing & pause & exit /b 1)
if not exist "package.json" (call npm init -y)
call npm install express node-fetch@2 cors
set "PORT=3000"
echo [INFO] starting Naver proxy on http://localhost:%PORT%
node "naver-proxy.js"
