#!/bin/bash
cd "$(dirname "$0")"

echo "================================================"
echo " US Stock Scanner"
echo "================================================"
echo ""

if [ ! -f "venv/bin/python" ]; then
    echo "[ERROR] venv not found. Please run setup first:"
    echo "        python3 -m venv venv"
    echo "        venv/bin/pip install -r requirements.txt"
    read -p "Press Enter to close..."
    exit 1
fi

if [ ! -f "venv/bin/streamlit" ]; then
    echo "[ERROR] streamlit not found in venv. Please install dependencies:"
    echo "        venv/bin/pip install -r requirements.txt"
    read -p "Press Enter to close..."
    exit 1
fi

echo "[1/3] Updating US market data..."
echo "      Universe: Nasdaq screener"
echo "      Filters: excludes ADR, ETF, funds, warrants, preferreds, trusts, bonds"
echo "      Price data: Yahoo Finance via yfinance"
echo "      Themes: USStockFlow market topics"
echo ""

venv/bin/python update_data.py
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Update failed. Check the messages above."
    read -p "Press Enter to close..."
    exit 1
fi

echo ""
echo "[2/3] Pushing data to GitHub..."
git add uptrend_results.json stock_concepts.json
if git diff --cached --quiet; then
    echo "      No data changes to commit."
else
    git commit -m "update US data"
    if [ $? -ne 0 ]; then
        echo ""
        echo "[WARNING] Git commit failed, but local data is updated."
    else
        git push
        if [ $? -ne 0 ]; then
            echo ""
            echo "[WARNING] GitHub push failed, but local data is updated."
        fi
    fi
fi

echo ""
echo "[3/3] Opening local Streamlit app..."
venv/bin/streamlit run app.py
