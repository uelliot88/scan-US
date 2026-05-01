import json
from datetime import datetime, timedelta

import requests


BASE_URL = "https://twstockflow.aihost.dev"
MARKETS = "tse,otc"
OUTPUT_FILE = "stock_concepts.json"


def fetch_json(path, params=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def build_stock_concepts():
    latest = fetch_json("/api/v1/meta/latest")
    themes_payload = fetch_json("/api/v1/themes/list", {"markets": MARKETS})

    stock_concepts = {}
    theme_count = 0
    for theme_row in themes_payload.get("themes", []):
        theme = str(theme_row.get("theme", "")).strip()
        if not theme:
            continue
        theme_count += 1
        for stock_id in theme_row.get("stock_ids", []):
            code = str(stock_id).strip()
            if not code:
                continue
            stock_concepts.setdefault(code, []).append(theme)

    for code, concepts in stock_concepts.items():
        stock_concepts[code] = sorted(set(concepts), key=concepts.index)

    tw_now = datetime.utcnow() + timedelta(hours=8)
    return {
        "source": BASE_URL,
        "source_endpoint": f"{BASE_URL}/api/v1/themes/list?markets={MARKETS}",
        "markets": MARKETS,
        "latest_trade_date": latest.get("latest_trade_date"),
        "generated_at": tw_now.strftime("%Y-%m-%d %H:%M:%S"),
        "theme_count": theme_count,
        "stock_count": len(stock_concepts),
        "stock_concepts": dict(sorted(stock_concepts.items())),
    }


def main():
    payload = build_stock_concepts()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(
        f"已更新 {OUTPUT_FILE}: "
        f"{payload['stock_count']} 檔股票、{payload['theme_count']} 個族群標籤來源"
    )


if __name__ == "__main__":
    main()
