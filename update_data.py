import sys
import io as _io
sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import yfinance as yf


# ==========================================
# 參數設定
# ==========================================
YEARS = 1.2
MIN_RISE_PCT = 0.20
MIN_DURATION = 5
LOOKBACK_PERIOD = 15
MAX_STOCKS = int(os.getenv('MAX_STOCKS', '0')) or None
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))
MIN_VOLUME_SHARES = int(os.getenv('MIN_VOLUME_SHARES', '500000'))
VOLUME_SURGE_RATIO = float(os.getenv('VOLUME_SURGE_RATIO', '1.6'))
SPY_SYMBOL = 'SPY'

NASDAQ_SCREENER_URL = (
    'https://api.nasdaq.com/api/screener/stocks'
    '?tableonly=true&limit=25&offset=0&download=true'
)


def load_concept_meta():
    try:
        with open('stock_concepts.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}

    return {
        'latest_trade_date': data.get('latest_trade_date', ''),
        'generated_at': data.get('generated_at', ''),
        'theme_count': data.get('theme_count', 0),
        'stock_count': data.get('stock_count', 0),
        'source': data.get('source', ''),
    }


def normalize_yahoo_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace('/', '-')


def is_common_equity(row: dict) -> bool:
    symbol = str(row.get('symbol', '')).strip().upper()
    name = str(row.get('name', '')).strip().lower()
    if not symbol or '^' in symbol:
        return False
    blocked_terms = (
        'warrant', 'unit', 'right', 'preferred', 'preference', 'depositary',
        'notes due', 'baby bond', 'etf', 'fund', 'trust', 'index',
    )
    return not any(term in name for term in blocked_terms)


def get_us_tickers():
    """抓取 Nasdaq screener 美股清單，回傳 tickers/name/sector/industry/country maps."""
    print('正在獲取美股清單（Nasdaq screener）...')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json,text/plain,*/*',
        'Origin': 'https://www.nasdaq.com',
        'Referer': 'https://www.nasdaq.com/market-activity/stocks/screener',
    }
    resp = requests.get(NASDAQ_SCREENER_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    rows = payload.get('data', {}).get('rows', [])

    tickers = []
    name_map = {}
    sector_map = {}
    industry_map = {}
    country_map = {}
    seen = set()

    for row in rows:
        if not is_common_equity(row):
            continue
        symbol = normalize_yahoo_symbol(row.get('symbol', ''))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        tickers.append(symbol)
        name_map[symbol] = str(row.get('name', '')).strip()
        sector_map[symbol] = str(row.get('sector', '')).strip()
        industry_map[symbol] = str(row.get('industry', '')).strip()
        country_map[symbol] = str(row.get('country', '')).strip()

    print(f'共找到 {len(tickers)} 檔美股普通股/ADR 候選標的')
    if MAX_STOCKS:
        print(f'測試模式：僅抽取前 {MAX_STOCKS} 檔股票進行分析')
        tickers = tickers[:MAX_STOCKS]

    return tickers, name_map, sector_map, industry_map, country_map


def safe_batch_download(tickers, start_date, end_date, batch_size=50):
    """批次下載 Yahoo Finance 價量資料。"""
    all_data = {}
    total_batches = (len(tickers) // batch_size) + (1 if len(tickers) % batch_size else 0)
    print(f'\n[下載] 準備將 {len(tickers)} 檔股票分為 {total_batches} 個批次下載...')

    for i in range(total_batches):
        batch = tickers[i * batch_size: (i + 1) * batch_size]
        if not batch:
            continue
        print(f' -> 正在下載第 {i + 1}/{total_batches} 批次 ({len(batch)} 檔)...', end=' ', flush=True)
        try:
            batch_data = yf.download(
                batch,
                start=start_date,
                end=end_date,
                group_by='ticker',
                progress=False,
                threads=True,
            )
            for symbol in batch:
                try:
                    df_sym = batch_data if len(batch) == 1 else batch_data[symbol]
                    if not df_sym.empty:
                        all_data[symbol] = df_sym.copy()
                except KeyError:
                    continue
            print('成功')
            time.sleep(1)
        except Exception as e:
            print(f'失敗 ({e})')
            print('等待 20 秒後繼續...')
            time.sleep(20)
    return all_data


def _build_ma_df(df):
    temp_df = pd.DataFrame(index=df.index)
    temp_df['Close'] = df['Close']
    temp_df['Low'] = df['Low']
    temp_df['MA10'] = temp_df['Close'].rolling(window=10).mean()
    temp_df['MA20'] = temp_df['Close'].rolling(window=20).mean()
    temp_df['MA60'] = temp_df['Close'].rolling(window=60).mean()
    half_year_ago = datetime.now() - timedelta(days=180)
    recent_df = temp_df[temp_df.index >= half_year_ago].dropna()
    return temp_df, recent_df


def _check_base(df, temp_df, recent_df):
    if len(df) < 120:
        return False

    latest_low = float(df['Low'].iloc[-1])
    if latest_low <= float(df['High'].iloc[-120:-90].max()):
        return False

    current_zone_low = float(df['Low'].iloc[-30:].min())
    low_60_ago = float(df['Low'].iloc[-60])
    zone_60_to_90_min = float(df['Low'].iloc[-90:-60].min())
    zone_120_to_90_min = float(df['Low'].iloc[-120:-90].min())
    if current_zone_low < zone_60_to_90_min or low_60_ago < zone_120_to_90_min:
        return False

    if len(recent_df) < 60:
        return False
    if (recent_df['Low'] < recent_df['MA60']).sum() > 60:
        return False

    valid_days = ((recent_df['MA10'] > recent_df['MA60']) & (recent_df['MA20'] > recent_df['MA60'])).sum()
    if valid_days / len(recent_df) < 0.25:
        return False

    if float(temp_df['Close'].iloc[-1]) <= float(temp_df['MA60'].iloc[-1]):
        return False

    return True


def check_type_a(df):
    """型態A：漲後整理 - 收盤 > MA60 且 MA10/MA20 均線糾結。"""
    temp_df, recent_df = _build_ma_df(df)
    if not _check_base(df, temp_df, recent_df):
        return False
    ma10 = float(temp_df['MA10'].iloc[-1])
    ma20 = float(temp_df['MA20'].iloc[-1])
    return abs(ma10 - ma20) / ma20 <= 0.03


def check_type_b(df):
    """型態B：多頭排列 - MA10 > MA20 > MA60。"""
    temp_df, recent_df = _build_ma_df(df)
    if not _check_base(df, temp_df, recent_df):
        return False
    ma10 = float(temp_df['MA10'].iloc[-1])
    ma20 = float(temp_df['MA20'].iloc[-1])
    ma60 = float(temp_df['MA60'].iloc[-1])
    return ma10 > ma20 > ma60


def identify_uptrend(df, symbol):
    if len(df) < LOOKBACK_PERIOD * 2:
        return []

    highs, lows = [], []
    for i in range(LOOKBACK_PERIOD, len(df) - LOOKBACK_PERIOD):
        window = df.iloc[i - LOOKBACK_PERIOD: i + LOOKBACK_PERIOD + 1]
        if float(df['High'].iloc[i]) == float(window['High'].max()):
            highs.append((i, float(df['High'].iloc[i]), df.index[i]))
        if float(df['Low'].iloc[i]) == float(window['Low'].min()):
            lows.append((i, float(df['Low'].iloc[i]), df.index[i]))

    segments = []
    used_highs = set()
    for low_idx, low_price, low_time in lows:
        candidates = [h for h in highs if h[0] > low_idx and h[0] not in used_highs]
        best_high = None
        best_rise = 0

        for high_idx, high_price, high_time in candidates:
            rise_pct = (high_price - low_price) / low_price
            duration = high_idx - low_idx
            if rise_pct < MIN_RISE_PCT or duration < MIN_DURATION:
                continue
            segment_data = df.iloc[low_idx + 1: high_idx]
            is_pure = len(segment_data) == 0 or float(segment_data['Low'].min()) > float(low_price)
            if is_pure and rise_pct > best_rise:
                best_rise = rise_pct
                best_high = (high_idx, high_price, high_time)

        if best_high:
            high_idx, high_price, high_time = best_high
            used_highs.add(high_idx)
            segments.append({
                'symbol': symbol,
                'start_date': low_time.strftime('%Y-%m-%d'),
                'end_date': high_time.strftime('%Y-%m-%d'),
                'start_price': round(float(low_price), 2),
                'end_price': round(float(high_price), 2),
                'rise_pct': round(float(best_rise), 4),
                'duration_days': int(high_idx - low_idx),
            })

    return segments


def check_volume(df) -> bool:
    """流動性：近 10 日均量達門檻。"""
    if len(df) < 10:
        return False
    return float(df['Volume'].iloc[-10:].mean()) >= MIN_VOLUME_SHARES


def check_vol_surge(df) -> bool:
    if len(df) < 20:
        return False
    vol_5 = float(df['Volume'].iloc[-5:].mean())
    vol_20 = float(df['Volume'].iloc[-20:].mean())
    return vol_20 > 0 and vol_5 >= vol_20 * VOLUME_SURGE_RATIO


def check_relative_strength(df, benchmark_df) -> bool:
    if benchmark_df is None or len(df) < 60 or len(benchmark_df) < 60:
        return False
    stock_return = float(df['Close'].iloc[-1] / df['Close'].iloc[-60] - 1)
    spy_return = float(benchmark_df['Close'].iloc[-1] / benchmark_df['Close'].iloc[-60] - 1)
    return stock_return > spy_return


def clean_downloaded_df(raw_df):
    if isinstance(raw_df.columns, pd.MultiIndex):
        raw_df.columns = raw_df.columns.get_level_values(0)
    clean_df = raw_df.dropna(subset=['High', 'Low', 'Close', 'Volume']).copy()
    clean_df = clean_df[clean_df['Volume'] > 0]
    return clean_df


def main():
    tickers, name_map, sector_map, industry_map, country_map = get_us_tickers()
    if not tickers:
        print('未獲取到任何股票代號，程式終止。')
        return

    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=YEARS * 365)).strftime('%Y-%m-%d')
    end_date = (now_utc + timedelta(days=1)).strftime('%Y-%m-%d')

    all_symbols = [SPY_SYMBOL] + [s for s in tickers if s != SPY_SYMBOL]
    data_dict = safe_batch_download(all_symbols, start_date, end_date, batch_size=BATCH_SIZE)
    benchmark_df = clean_downloaded_df(data_dict[SPY_SYMBOL]) if SPY_SYMBOL in data_dict else None

    final_payload = {}
    failed_count = 0
    filtered_out_by_ma = 0
    filtered_out_by_segment = 0
    filtered_out_by_volume = 0

    print('\n開始執行三重過濾並打包繪圖數據...')

    for symbol in tickers:
        try:
            if symbol not in data_dict:
                continue

            clean_df = clean_downloaded_df(data_dict[symbol])
            if clean_df.empty:
                continue

            is_a = check_type_a(clean_df)
            is_b = check_type_b(clean_df)
            if not (is_a or is_b):
                filtered_out_by_ma += 1
                continue
            stock_type = 'A' if is_a else 'B'

            segments = identify_uptrend(clean_df, symbol)
            if not segments:
                filtered_out_by_segment += 1
                continue

            if not check_volume(clean_df):
                filtered_out_by_volume += 1
                continue

            vol_surge = bool(check_vol_surge(clean_df))
            rs_spy = bool(check_relative_strength(clean_df, benchmark_df))

            ma10 = clean_df['Close'].rolling(window=10).mean()
            ma20 = clean_df['Close'].rolling(window=20).mean()
            ma60 = clean_df['Close'].rolling(window=60).mean()
            plot_df = clean_df.tail(200).copy()

            def fmt_ma(series):
                return [round(float(x), 2) if pd.notna(x) else None for x in series.tail(200)]

            final_payload[symbol] = {
                'type': stock_type,
                'sector': sector_map.get(symbol, ''),
                'industry': industry_map.get(symbol, ''),
                'country': country_map.get(symbol, ''),
                'vol_surge': vol_surge,
                'rs_spy': rs_spy,
                'date': plot_df.index.strftime('%m-%d').tolist(),
                'open': [round(float(x), 2) for x in plot_df['Open']],
                'high': [round(float(x), 2) for x in plot_df['High']],
                'low': [round(float(x), 2) for x in plot_df['Low']],
                'close': [round(float(x), 2) for x in plot_df['Close']],
                'volume': [int(x) for x in plot_df['Volume']],
                'ma10': fmt_ma(ma10),
                'ma20': fmt_ma(ma20),
                'ma60': fmt_ma(ma60),
            }

        except Exception:
            failed_count += 1
            continue

    output = {
        'market': 'US',
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_symbols_found': len(final_payload),
        'source': {
            'universe': 'Nasdaq screener',
            'price': 'Yahoo Finance via yfinance',
            'reference': 'https://usstockflow.aihost.dev/',
        },
        'name_map': {k: name_map.get(k, '') for k in final_payload},
        'sector_map': {k: sector_map.get(k, '') for k in final_payload},
        'industry_map': {k: industry_map.get(k, '') for k in final_payload},
        'country_map': {k: country_map.get(k, '') for k in final_payload},
        'concept_meta': load_concept_meta(),
        'results': final_payload,
    }

    with open('uptrend_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    rs_count = sum(1 for v in final_payload.values() if v.get('rs_spy'))
    vol_count = sum(1 for v in final_payload.values() if v.get('vol_surge'))
    print('\n分析完成！')
    print('[報告] 淘汰報告：')
    print(f'   - {filtered_out_by_ma} 檔因均線條件不符被淘汰')
    print(f'   - {filtered_out_by_segment} 檔因無 >=20% 有效波段被淘汰')
    print(f'   - {filtered_out_by_volume} 檔因成交量不足被淘汰')
    print(f'[標註] 60 日相對 SPY 強勢：{rs_count} 檔，放量：{vol_count} 檔')
    print(f'[結果] 最終找到 {len(final_payload)} 檔符合條件個股，K 線已打包進 uptrend_results.json')
    if failed_count > 0:
        print(f'有 {failed_count} 檔股票在計算時發生例外狀況被跳過')


if __name__ == '__main__':
    main()
