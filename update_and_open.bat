@echo off
chcp 65001 >nul
title US Stock Scanner
cd /d "%~dp0"

echo ================================================
echo  US Stock Scanner
echo ================================================
echo.
echo [1/3] Updating US market data...
echo       Universe: Nasdaq screener
echo       Price data: Yahoo Finance via yfinance
echo.

venv\Scripts\python update_data.py
if errorlevel 1 (
    echo.
    echo [ERROR] Update failed. Check the messages above.
    pause
    exit /b 1
)

echo.
echo [2/3] Pushing data to GitHub...
git add uptrend_results.json stock_concepts.json
git commit -m "update US data"
git push
if errorlevel 1 (
    echo.
    echo [WARNING] GitHub push failed, but local data is updated.
)

echo.
echo [3/3] Opening local Streamlit app...
venv\Scripts\streamlit run app.py

echo.
echo ================================================
echo  Done.
echo ================================================
pause
