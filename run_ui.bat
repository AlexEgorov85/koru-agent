@echo off
set STREAMLIT_SERVER_HEADLESS=true
python -m streamlit run "%~dp0web_ui\app.py" -- --server.port 8501 --server.headless true --server.address 0.0.0.0