@echo off
setlocal
cd /d "%~dp0..\backend"
if not exist .venv (python -m venv .venv)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if not exist .env copy .env.example .env
python app.py
