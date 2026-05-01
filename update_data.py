import sys
import io as _io
sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import numpy as np
import json
import requests
import io
import time
from datetime import datetime, timedelta

# ==========================================
# 參數設定
# ==========================================
YEARS = 1.2
MIN_RISE_PCT = 0.20         # 波段最小漲幅 20%
MIN_DURATION = 5            # 最少持續 5 天
LOOKBACK_PERIOD = 15        # 找尋局部高低點的視窗大小
MAX_STOCKS = None           # None 代表跑全市場
BATCH_SIZE = 50             # 每次向 Yahoo 請求的股票數量
MIN_VOLUME_LOTS = 800       # 最小成交量（張），1張=1000股
VOLUME_SURGE_RATIO = 1.3    # 量能增加倍數（近5日均量 ÷ 近20日均量）
INST_LOOKUP_DAYS = 7        # 法人資料回溯天數


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
    }


def get_tw_tickers():
    """抓取台灣上市(TW)與上櫃(TWO)股票代號，回傳 (tickers list, name_map dict, sector_map dict)"""
    print("正在獲取台股上市櫃清單...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    res_twse = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", headers=headers, timeout=15)
    df_twse = pd.read_html(io.StringIO(res_twse.text))[0]
    twse_tickers = []
    name_map = {}
    sector_map = {}
    for _, row in df_twse.iterrows():
        parts = str(row[0]).split()
        if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4:
            ticker = parts[0] + '.TW'
            twse_tickers.append(ticker)
            name_map[ticker] = parts[1]
            sector_map[ticker] = str(row[4]).strip() if pd.notna(row[4]) else ''

    res_tpex = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", headers=headers, timeout=15)
    df_tpex = pd.read_html(io.StringIO(res_tpex.text))[0]
    tpex_tickers = []
    for _, row in df_tpex.iterrows():
        parts = str(row[0]).split()
        if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4:
            ticker = parts[0] + '.TWO'
            tpex_tickers.append(ticker)
            name_map[ticker] = parts[1]
            sector_map[ticker] = str(row[4]).strip() if pd.notna(row[4]) else ''

    all_tickers = twse_tickers + tpex_tickers
    print(f"共找到 {len(twse_tickers)} 檔上市, {len(tpex_tickers)} 檔上櫃")

    if MAX_STOCKS:
        print(f"⚠️ 測試模式：僅抽取前 {MAX_STOCKS} 檔股票進行分析")
        return all_tickers[:MAX_STOCKS], name_map, sector_map
    return all_tickers, name_map, sector_map


def safe_batch_download(tickers, start_date, end_date, batch_size=50):
    """【批次下載與防護冷卻機制】"""
    all_data = {}
    total_batches = (len(tickers) // batch_size) + (1 if len(tickers) % batch_size != 0 else 0)
    print(f"\n[下載] 準備將 {len(tickers)} 檔股票分為 {total_batches} 個批次進行下載...")

    for i in range(total_batches):
        batch = tickers[i * batch_size: (i + 1) * batch_size]
        if not batch:
            continue
        print(f" ➤ 正在下載第 {i+1}/{total_batches} 批次 ({len(batch)} 檔)...", end=" ", flush=True)
        try:
            batch_data = yf.download(batch, start=start_date, end=end_date, group_by='ticker', progress=False)
            for symbol in batch:
                try:
                    df_sym = batch_data if len(batch) == 1 else batch_data[symbol]
                    if not df_sym.empty:
                        all_data[symbol] = df_sym.copy()
                except KeyError:
                    continue
            print("✅ 成功")
            time.sleep(2)
        except Exception as e:
            print(f"❌ 失敗 ({str(e)})")
            print(" ⏳ 疑似觸發防封鎖機制，強制休息 30 秒後繼續...")
            time.sleep(30)
    return all_data


def _build_ma_df(df):
    """計算均線並回傳 (temp_df, recent_df)，供型態判斷共用"""
    temp_df = pd.DataFrame(index=df.index)
    temp_df['Close'] = df['Close']
    temp_df['Low']   = df['Low']
    temp_df['MA10']  = temp_df['Close'].rolling(window=10).mean()
    temp_df['MA20']  = temp_df['Close'].rolling(window=20).mean()
    temp_df['MA60']  = temp_df['Close'].rolling(window=60).mean()
    half_year_ago = datetime.now() - timedelta(days=180)
    recent_df = temp_df[temp_df.index >= half_year_ago].dropna()
    return temp_df, recent_df


def _check_base(df, temp_df, recent_df):
    """共同基底條件：底部墊高 + 季線健康 + 收盤 > MA60"""
    if len(df) < 120:
        return False

    # 底部墊高
    latest_low = float(df['Low'].iloc[-1])
    if latest_low <= float(df['High'].iloc[-120:-90].max()):
        return False
    current_zone_low    = float(df['Low'].iloc[-30:].min())
    low_60_ago          = float(df['Low'].iloc[-60])
    zone_60_to_90_min   = float(df['Low'].iloc[-90:-60].min())
    zone_120_to_90_min  = float(df['Low'].iloc[-120:-90].min())
    if current_zone_low < zone_60_to_90_min or low_60_ago < zone_120_to_90_min:
        return False

    # 季線壓制排除
    if len(recent_df) < 60:
        return False
    if (recent_df['Low'] < recent_df['MA60']).sum() > 60:
        return False

    # 近半年 MA10/MA20 同站 MA60 比例 ≥ 25%
    valid_days = ((recent_df['MA10'] > recent_df['MA60']) & (recent_df['MA20'] > recent_df['MA60'])).sum()
    if valid_days / len(recent_df) < 0.25:
        return False

    # 收盤站上 MA60
    if float(temp_df['Close'].iloc[-1]) <= float(temp_df['MA60'].iloc[-1]):
        return False

    return True


def check_type_a(df):
    """型態A：漲後整理 — 收盤 > MA60 且 MA10/MA20 均線糾結（差距 ≤ 3%）"""
    temp_df, recent_df = _build_ma_df(df)
    if not _check_base(df, temp_df, recent_df):
        return False
    ma10 = float(temp_df['MA10'].iloc[-1])
    ma20 = float(temp_df['MA20'].iloc[-1])
    return abs(ma10 - ma20) / ma20 <= 0.03


def check_type_b(df):
    """型態B：多頭排列趨勢中 — MA10 > MA20 > MA60"""
    temp_df, recent_df = _build_ma_df(df)
    if not _check_base(df, temp_df, recent_df):
        return False
    ma10 = float(temp_df['MA10'].iloc[-1])
    ma20 = float(temp_df['MA20'].iloc[-1])
    ma60 = float(temp_df['MA60'].iloc[-1])
    return ma10 > ma20 > ma60


def identify_uptrend(df, symbol):
    """【微觀波段識別演算法】"""
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
        if not candidates:
            continue

        best_high = None
        best_rise = 0

        for high_idx, high_price, high_time in candidates:
            rise_pct = (high_price - low_price) / low_price
            duration = high_idx - low_idx

            if rise_pct >= MIN_RISE_PCT and duration >= MIN_DURATION:
                segment_data = df.iloc[low_idx + 1: high_idx]
                if len(segment_data) == 0:
                    is_pure = True
                else:
                    min_in_segment = float(segment_data['Low'].min())
                    is_pure = min_in_segment > float(low_price)

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
                'duration_days': int(high_idx - low_idx)
            })

    return segments


# ==========================================
# 法人買賣超資料（外資 / 投信 分開追蹤）
# ==========================================

def get_recent_trading_dates(n=7):
    """取得最近 n 個交易日（排除週末，假日由 API 回應判斷）"""
    dates = []
    d = datetime.now()
    attempts = 0
    while len(dates) < n and attempts < 30:
        d -= timedelta(days=1)
        attempts += 1
        if d.weekday() < 5:
            dates.append(d)
    return sorted(dates)


def fetch_twse_institutional(date: datetime):
    """
    抓取上市外資 / 投信買賣超（TWSE T86）
    回傳 {stock_code: {'foreign': net, 'trust': net}}
    """
    date_str = date.strftime('%Y%m%d')
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALL"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if data.get('stat') != 'OK' or 'data' not in data:
            return {}
        result = {}
        for row in data['data']:
            code = str(row[0]).strip()
            try:
                foreign = int(str(row[4]).replace(',', '').replace('+', '').strip())   # 外資買賣超
                trust   = int(str(row[10]).replace(',', '').replace('+', '').strip())  # 投信買賣超
                result[code] = {'foreign': foreign, 'trust': trust}
            except (ValueError, IndexError):
                continue
        return result
    except Exception:
        return {}


def fetch_tpex_institutional(date: datetime):
    """
    抓取上櫃外資 / 投信買賣超（TPEX）
    回傳 {stock_code: {'foreign': net, 'trust': net}}
    """
    roc_year = date.year - 1911
    date_str = f"{roc_year}/{date.strftime('%m/%d')}"
    url = (
        f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/"
        f"3itrade_hedge_result.php?l=zh-tw&se=EW&t=D&d={date_str}"
    )
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if 'aaData' not in data:
            return {}
        result = {}
        for row in data['aaData']:
            code = str(row[0]).strip()
            try:
                foreign = int(float(str(row[4]).replace(',', '').replace('+', '').strip()) * 1000)   # 外資（千股）
                trust   = int(float(str(row[10]).replace(',', '').replace('+', '').strip()) * 1000)  # 投信（千股）
                result[code] = {'foreign': foreign, 'trust': trust}
            except (ValueError, IndexError):
                continue
        return result
    except Exception:
        return {}


def build_institutional_data(n_days=7):
    """
    建立最近 n_days 個交易日的外資/投信買賣超序列
    回傳: {stock_code: {'foreign': [...], 'trust': [...]}}
    """
    trading_dates = get_recent_trading_dates(n_days)
    daily_records = {}

    print(f"\n[法人] 正在抓取最近 {n_days} 個交易日的法人資料...")
    for d in trading_dates:
        twse = fetch_twse_institutional(d)
        tpex = fetch_tpex_institutional(d)
        merged = {**twse, **tpex}
        daily_records[d] = merged
        status = f"{len(merged)} 檔" if merged else "無資料(假日)"
        print(f"   {d.strftime('%Y-%m-%d')} → {status}")
        time.sleep(0.8)

    all_codes = set()
    for day_data in daily_records.values():
        all_codes.update(day_data.keys())

    result = {}
    for code in all_codes:
        result[code] = {
            'foreign': [daily_records[d].get(code, {}).get('foreign', 0) for d in trading_dates],
            'trust':   [daily_records[d].get(code, {}).get('trust',   0) for d in trading_dates],
        }

    valid_days = sum(1 for d in trading_dates if daily_records[d])
    print(f"✅ 法人資料載入完成，共 {valid_days} 個有效交易日，涵蓋 {len(result)} 檔個股")
    return result


def get_institutional_flags(stock_code: str, inst_data: dict) -> dict:
    """
    回傳外資、投信是否符合買超條件（近2日連續買超 + 近5日淨額為正）
    {'foreign': bool, 'trust': bool}
    """
    code = stock_code.split('.')[0]

    def passes(series):
        if len(series) < 5:
            return False
        return all(v > 0 for v in series[-2:]) and sum(series[-5:]) > 0

    if code not in inst_data:
        return {'foreign': False, 'trust': False}

    return {
        'foreign': passes(inst_data[code]['foreign']),
        'trust':   passes(inst_data[code]['trust']),
    }


def check_volume(df) -> bool:
    """流動性：近10日均量 ≥ 800張"""
    if len(df) < 10:
        return False
    vol_10 = df['Volume'].iloc[-10:].mean()
    return vol_10 >= MIN_VOLUME_LOTS * 1000


def check_vol_surge(df) -> bool:
    """放量標註：近5日均量 ≥ 近20日均量 × 1.6"""
    if len(df) < 20:
        return False
    vol_5  = df['Volume'].iloc[-5:].mean()
    vol_20 = df['Volume'].iloc[-20:].mean()
    return vol_20 > 0 and vol_5 >= vol_20 * 1.6


def main():
    tickers, name_map, sector_map = get_tw_tickers()
    if not tickers:
        print("未獲取到任何股票代號，程式終止。")
        return

    inst_data = build_institutional_data(INST_LOOKUP_DAYS)

    tw_now = datetime.utcnow() + timedelta(hours=8)
    start_date = (tw_now - timedelta(days=YEARS * 365)).strftime('%Y-%m-%d')
    end_date = (tw_now + timedelta(days=1)).strftime('%Y-%m-%d')

    data_dict = safe_batch_download(tickers, start_date, end_date, batch_size=BATCH_SIZE)

    final_payload = {}
    failed_count = 0
    filtered_out_by_ma = 0
    filtered_out_by_segment = 0
    filtered_out_by_volume = 0

    print("\n開始執行三重過濾並打包繪圖數據...")

    for symbol in tickers:
        try:
            if symbol not in data_dict:
                continue

            raw_df = data_dict[symbol].copy()
            if isinstance(raw_df.columns, pd.MultiIndex):
                raw_df.columns = raw_df.columns.get_level_values(0)

            clean_df = raw_df.dropna(subset=['High', 'Low', 'Close']).copy()
            if len(clean_df) == 0:
                continue

            # 第一重：均線濾網（型態A 或 型態B）
            is_a = check_type_a(clean_df)
            is_b = check_type_b(clean_df)
            if not (is_a or is_b):
                filtered_out_by_ma += 1
                continue
            stock_type = 'A' if is_a else 'B'

            # 第二重：波段識別（≥20%，不跌回起漲點）
            segments = identify_uptrend(clean_df, symbol)
            if not segments:
                filtered_out_by_segment += 1
                continue

            # 第三重：成交量條件
            if not check_volume(clean_df):
                filtered_out_by_volume += 1
                continue

            # 法人標註（不篩選，僅記錄）
            inst_flags = get_institutional_flags(symbol, inst_data)

            # 放量標註（不篩選，僅記錄）
            vol_surge = bool(check_vol_surge(clean_df))

            # 用完整歷史計算均線，只取後 200 根 K 線輸出
            ma10 = clean_df['Close'].rolling(window=10).mean()
            ma20 = clean_df['Close'].rolling(window=20).mean()
            ma60 = clean_df['Close'].rolling(window=60).mean()

            plot_df = clean_df.tail(200).copy()
            def fmt_ma(series):
                return [round(float(x), 2) if pd.notna(x) else None for x in series.tail(200)]

            k_data = {
                'type':         stock_type,
                'sector':       sector_map.get(symbol, ''),
                'inst_foreign': inst_flags['foreign'],
                'inst_trust':   inst_flags['trust'],
                'vol_surge':    vol_surge,
                'date':   plot_df.index.strftime('%m-%d').tolist(),
                'open':   [round(float(x), 2) for x in plot_df['Open']],
                'high':   [round(float(x), 2) for x in plot_df['High']],
                'low':    [round(float(x), 2) for x in plot_df['Low']],
                'close':  [round(float(x), 2) for x in plot_df['Close']],
                'volume': [int(x) for x in plot_df['Volume']],
                'ma10':   fmt_ma(ma10),
                'ma20':   fmt_ma(ma20),
                'ma60':   fmt_ma(ma60),
            }
            final_payload[symbol] = k_data

        except Exception:
            failed_count += 1
            continue

    tw_time = datetime.utcnow() + timedelta(hours=8)
    output = {
        'last_updated': tw_time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_symbols_found': len(final_payload),
        'name_map':   {k: name_map.get(k, '')   for k in final_payload},
        'sector_map': {k: sector_map.get(k, '') for k in final_payload},
        'concept_meta': load_concept_meta(),
        'results': final_payload
    }

    with open('uptrend_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析完成！")
    inst_foreign_count = sum(1 for v in final_payload.values() if v.get('inst_foreign'))
    inst_trust_count   = sum(1 for v in final_payload.values() if v.get('inst_trust'))
    print(f"[報告] 淘汰報告：")
    print(f"   - {filtered_out_by_ma}      檔因【均線條件不符】被淘汰")
    print(f"   - {filtered_out_by_segment} 檔因【無 ≥20% 有效波段】被淘汰")
    print(f"   - {filtered_out_by_volume}  檔因【成交量不足或未放量】被淘汰")
    print(f"[法人標註] 外資買超：{inst_foreign_count} 檔，投信買超：{inst_trust_count} 檔")
    print(f"[結果] 最終找到 {len(final_payload)} 檔符合條件個股，K 線已打包進 uptrend_results.json")
    if failed_count > 0:
        print(f"⚠️ 有 {failed_count} 檔股票在計算時發生例外狀況被跳過")


if __name__ == "__main__":
    main()
