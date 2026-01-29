@echo off
setlocal EnableDelayedExpansion

rem 1) check node
where node >nul 2>&1 || (echo [ERROR] node not found & pause & exit /b 1)

rem 2) require yf-proxy.js
if not exist "yf-proxy.js" (echo [ERROR] yf-proxy.js missing & pause & exit /b 1)

rem 3) npm init if needed
if not exist "package.json" (call npm init -y)

rem 4) deps
call npm install express node-fetch@2 cors

rem 5) run
set "PORT=3000"
echo [INFO] starting YF proxy on http://localhost:%PORT%
node "yf-proxy.js"
