@echo off
chcp 65001 >nul
title US Stock Scanner
cd /d "%~dp0"

echo ================================================
echo  US Stock Scanner
echo ================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Please run setup first:
    echo         python -m venv venv
    echo         venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "venv\Scripts\streamlit.exe" (
    echo [ERROR] streamlit not found in venv. Please install dependencies:
    echo         venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/3] Updating US market data...
echo       Universe: Nasdaq screener
echo       Filters: excludes ADR, ETF, funds, warrants, preferreds, trusts, bonds
echo       Price data: Yahoo Finance via yfinance
echo       Themes: USStockFlow market topics
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
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "update US data"
    if errorlevel 1 (
        echo.
        echo [WARNING] Git commit failed, but local data is updated.
    ) else (
        git push
        if errorlevel 1 (
            echo.
            echo [WARNING] GitHub push failed, but local data is updated.
        )
    )
) else (
    echo       No data changes to commit.
)

echo.
echo [3/3] Opening local Streamlit app...
venv\Scripts\streamlit run app.py

echo.
echo ================================================
echo  Done.
echo ================================================
pause
