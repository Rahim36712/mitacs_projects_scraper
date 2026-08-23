@echo off
cd /d "%~dp0"
python "%~dp0mitacs_scraper\main.py" ui --host 127.0.0.1 --port 5001
