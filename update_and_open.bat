@echo off
chcp 65001 >nul
title Taiwan Stock Scanner
cd /d "%~dp0"

echo ================================================
echo  Taiwan Stock Scanner
echo ================================================
echo.
echo [1/4] Updating concept tags...
venv\Scripts\python update_stock_concepts.py
if errorlevel 1 (
    echo.
    echo [WARNING] Concept tag update failed. Continuing with existing local concept data.
)

echo.
echo [2/4] Updating data (takes ~10 mins)...
echo       Downloading 1967 stocks in 40 batches.
echo.

venv\Scripts\python update_data.py
if errorlevel 1 (
    echo.
    echo [ERROR] Update failed. Check the messages above.
    pause
    exit /b 1
)

echo.
echo [3/4] Pushing to GitHub...
git add uptrend_results.json stock_concepts.json
git commit -m "update data"
git push
if errorlevel 1 (
    echo.
    echo [WARNING] GitHub push failed, but local data is updated.
)

echo.
echo [4/4] Opening browser...
start "" "https://scan-tw.streamlit.app/"

echo.
echo ================================================
echo  Done! Browser opened.
echo  Press any key to close this window.
echo ================================================
pause
