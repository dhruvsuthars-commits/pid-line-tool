@echo off
cd /d "%~dp0\pid-line-tool"
if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
) else (
  echo Virtual environment not found at venv\Scripts\activate.bat
  exit /b 1
)
python app.py
