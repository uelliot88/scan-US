import json
import io
from datetime import datetime, timedelta

import pandas as pd
import requests


BASE_URL = "https://twstockflow.aihost.dev"
MARKETS = "tse,otc"
OUTPUT_FILE = "stock_concepts.json"
HOLDINGS_BATCH_SIZE = 120


def fetch_json(path, params=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def get_listed_stock_ids():
    stock_ids = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    for mode in (2, 4):
        response = requests.get(
            "https://isin.twse.com.tw/isin/C_public.jsp",
            params={"strMode": mode},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        table = pd.read_html(io.StringIO(response.text))[0]
        for _, row in table.iterrows():
            parts = str(row[0]).split()
            if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4:
                stock_ids.add(parts[0])

    return sorted(stock_ids)


def add_unique(concepts, theme):
    theme = str(theme or "").strip()
    if theme and theme not in concepts:
        concepts.append(theme)


def enrich_from_holdings_watchlist(stock_concepts, stock_ids):
    enriched_count = 0
    for start in range(0, len(stock_ids), HOLDINGS_BATCH_SIZE):
        batch = stock_ids[start:start + HOLDINGS_BATCH_SIZE]
        payload = fetch_json(
            "/api/v1/themes/holdings-watchlist",
            {"stock_ids": ",".join(batch), "window": "1d", "markets": MARKETS},
        )

        for row in payload.get("holdings", []):
            code = str(row.get("stock_id", "")).strip()
            if not code:
                continue

            before = len(stock_concepts.get(code, []))
            concepts = stock_concepts.setdefault(code, [])
            add_unique(concepts, row.get("primary_theme"))
            for theme in row.get("theme_groups") or []:
                add_unique(concepts, theme)

            if len(concepts) > before:
                enriched_count += 1

    return enriched_count


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
            add_unique(stock_concepts.setdefault(code, []), theme)

    stock_ids = get_listed_stock_ids()
    enriched_count = enrich_from_holdings_watchlist(stock_concepts, stock_ids)

    tw_now = datetime.utcnow() + timedelta(hours=8)
    return {
        "source": BASE_URL,
        "source_endpoints": [
            f"{BASE_URL}/api/v1/themes/list?markets={MARKETS}",
            f"{BASE_URL}/api/v1/themes/holdings-watchlist?stock_ids=...&window=1d&markets={MARKETS}",
        ],
        "markets": MARKETS,
        "latest_trade_date": latest.get("latest_trade_date"),
        "generated_at": tw_now.strftime("%Y-%m-%d %H:%M:%S"),
        "theme_count": theme_count,
        "listed_stock_count": len(stock_ids),
        "enriched_stock_count": enriched_count,
        "stock_count": len(stock_concepts),
        "stock_concepts": dict(sorted(stock_concepts.items())),
    }


def main():
    payload = build_stock_concepts()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(
        f"已更新 {OUTPUT_FILE}: "
        f"{payload['stock_count']} 檔股票、{payload['theme_count']} 個市場主題來源，"
        f"補齊 {payload['enriched_stock_count']} 檔個股主題"
    )


if __name__ == "__main__":
    main()
