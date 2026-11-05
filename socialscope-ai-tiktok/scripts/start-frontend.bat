@echo off
setlocal
cd /d "%~dp0..\frontend"
if not exist node_modules (call npm install)
call npm run dev -- --host 127.0.0.1 --strictPort
