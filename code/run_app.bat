@echo off
cd /d "%~dp0"
start "" cmd /c "timeout /t 2 >nul && start http://localhost:8501"
python -m streamlit run app.py --server.headless=false --server.port 8501
pause
