@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python -m pytest engine -q || exit /b 1
pyinstaller carbondelta.spec --noconfirm --clean
