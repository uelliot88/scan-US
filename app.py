import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import html
from urllib.parse import quote, unquote

APP_VERSION = "1.0"

# ==========================================
# 頁面與底色初始化
# ==========================================
st.set_page_config(page_title="美股掃圖", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 0rem; }

    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #ffffff !important;
    }

    .stApp * {
        color: #000000 !important;
        font-family: "Arial", sans-serif !important;
    }

    [data-testid="stSidebar"] { display: none; }
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }

    .pagination-nav {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 14px;
        font-size: 1rem;
        line-height: 1.6;
        padding: 4px 0 10px;
    }
    .pagination-nav a {
        color: #000000 !important;
        text-decoration: none !important;
        padding: 0 2px;
    }
    .pagination-nav a:hover {
        text-decoration: underline !important;
    }
    .pagination-nav .current-page {
        font-weight: 900;
        text-decoration: underline;
    }
    .pagination-nav .disabled-page {
        opacity: 0.45;
    }
    .stock-title {
        position: relative;
        display: inline-block;
        font-weight: 900;
        cursor: help;
    }
    .stock-title .stock-tooltip {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        z-index: 20;
        left: 0;
        top: 1.8rem;
        width: max-content;
        max-width: 320px;
        padding: 8px 10px;
        border: 1px solid #d9d9d9;
        border-radius: 4px;
        background: #ffffff;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.14);
        font-size: 0.85rem;
        font-weight: 400;
        line-height: 1.5;
        white-space: normal;
    }
    .stock-title:hover .stock-tooltip {
        visibility: visible;
        opacity: 1;
    }
    .theme-board {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 18px;
        margin: 10px 0 14px;
    }
    .theme-panel-title {
        font-size: 0.95rem;
        font-weight: 900;
        margin: 0 0 7px;
    }
    .theme-block-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 8px;
    }
    .theme-block {
        display: block;
        min-height: 70px;
        padding: 8px 9px;
        border: 1px solid #d9d9d9;
        border-radius: 6px;
        background: #ffffff;
        text-decoration: none !important;
    }
    .theme-block:hover {
        border-color: #000000;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    }
    .theme-block.active {
        border: 2px solid #000000;
    }
    .theme-block-name {
        display: block;
        font-size: 0.85rem;
        font-weight: 900;
        line-height: 1.25;
        margin-bottom: 5px;
        word-break: break-word;
    }
    .theme-block-meta {
        display: block;
        font-size: 0.75rem;
        line-height: 1.35;
    }
    .theme-strong .theme-block-meta strong {
        color: #008F39 !important;
    }
    .theme-weak .theme-block-meta strong {
        color: #E32636 !important;
    }
    .theme-selected-bar {
        font-size: 0.9rem;
        font-weight: 800;
        margin: 8px 0 12px;
    }
    .theme-selected-bar a {
        color: #000000 !important;
        text-decoration: underline !important;
    }
    @media (max-width: 900px) {
        .theme-board { grid-template-columns: 1fr; }
        .theme-block-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 載入 JSON 資料
# ==========================================
def load_analysis_results():
    try:
        with open('uptrend_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def load_stock_notes():
    try:
        with open('stock_notes.json', 'r', encoding='utf-8') as f:
            notes = json.load(f)
            return notes if isinstance(notes, dict) else {}
    except FileNotFoundError:
        return {}

def load_stock_concepts_payload():
    try:
        with open('stock_concepts.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}

def load_stock_concepts():
    data = load_stock_concepts_payload()
    concepts = data.get('stock_concepts', data) if isinstance(data, dict) else {}
    return concepts if isinstance(concepts, dict) else {}

data_store = load_analysis_results()

if not data_store or 'results' not in data_store:
    st.error("找不到分析數據或格式錯誤，請先執行 update_data.py")
    st.stop()

# ==========================================
# 2. 標題與更新時間
# ==========================================
last_updated = data_store.get('last_updated', '未知')

st.markdown(f"""
    <div style='display: flex; justify-content: space-between; align-items: baseline;
                border-bottom: 2px solid #000000; padding-top: 25px; padding-bottom: 5px; margin-bottom: 10px;'>
        <div style='font-size: 2.2rem; font-weight: 900; color: #000000; line-height: 1.2;'>美股掃圖</div>
        <div style='font-size: 0.9rem; font-weight: 800; color: #000000;'>版本：{APP_VERSION} ｜ 更新：{last_updated}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 準備渲染資料
# ==========================================
all_results = data_store['results']
name_map = data_store.get('name_map', {})
sector_map = data_store.get('sector_map', {})
industry_map = data_store.get('industry_map', {})
country_map = data_store.get('country_map', {})
business_map = data_store.get('business_map', {})
stock_notes = load_stock_notes()
stock_concepts_payload = load_stock_concepts_payload()
stock_concepts = load_stock_concepts()
stock_theme_strength = stock_concepts_payload.get('theme_strength', {})
stock_theme_details = stock_concepts_payload.get('theme_details', {})

SECTOR_ZH = {
    'Basic Materials': '原物料',
    'Communication Services': '通訊服務',
    'Consumer Discretionary': '非必需消費',
    'Consumer Staples': '民生消費',
    'Consumer Cyclical': '景氣循環消費',
    'Energy': '能源',
    'Finance': '金融',
    'Financial Services': '金融服務',
    'Health Care': '醫療保健',
    'Healthcare': '醫療保健',
    'Industrials': '工業',
    'Miscellaneous': '其他',
    'Real Estate': '不動產',
    'Technology': '科技',
    'Telecommunications': '電信',
    'Utilities': '公用事業',
}

INDUSTRY_ZH = {
    'Accident &Health Insurance': '意外與健康保險',
    'Advertising': '廣告',
    'Aerospace': '航太',
    'Agricultural Chemicals': '農業化學',
    'Air Freight/Delivery Services': '航空貨運與快遞服務',
    'Aluminum': '鋁業',
    'Apparel': '服飾',
    'Auto Manufacturing': '汽車製造',
    'Auto Parts': '汽車零組件',
    'Auto Parts:O.E.M.': '汽車零組件：原廠代工',
    'Banks': '銀行',
    'Beverages (Production/Distribution)': '飲料生產與通路',
    'Biotechnology': '生物科技',
    'Biotechnology: Biological Products (No Diagnostic Substances)': '生物科技：生物製品（非診斷試劑）',
    'Biotechnology: Electromedical & Electrotherapeutic Apparatus': '生物科技：電子醫療與電療設備',
    'Biotechnology: In Vitro & In Vivo Diagnostic Substances': '生物科技：體外與體內診斷試劑',
    'Biotechnology: Laboratory Analytical Instruments': '生物科技：實驗室分析儀器',
    'Biotechnology: Pharmaceutical Preparations': '生物科技：藥品製劑',
    'Broadcasting': '廣播媒體',
    'Building Materials': '建材',
    'Building Products': '建築產品',
    'Business Services': '商業服務',
    'Cable & Other Pay Television Services': '有線與付費電視服務',
    'Catalog/Specialty Distribution': '型錄與專業通路',
    'Chemicals': '化學品',
    'Clothing/Shoe/Accessory Stores': '服飾、鞋類與配件零售',
    'Commercial Banks': '商業銀行',
    'Computer Communications Equipment': '電腦通訊設備',
    'Computer Manufacturing': '電腦製造',
    'Computer peripheral equipment': '電腦周邊設備',
    'Computer Software': '電腦軟體',
    'Computer Software: Prepackaged Software': '電腦軟體：套裝軟體',
    'Computer Software: Programming Data Processing': '電腦軟體：程式設計與資料處理',
    'Construction/Ag Equipment/Trucks': '工程、農業設備與卡車',
    'Consumer Electronics': '消費電子',
    'Consumer Electronics/Appliances': '消費電子與家電',
    'Consumer Specialties': '消費專用品',
    'Department/Specialty Retail Stores': '百貨與專門零售店',
    'Diversified Commercial Services': '多元商業服務',
    'Drug Manufacturers': '製藥',
    'EDP Services': '資料處理服務',
    'Electric Utilities: Central': '電力公用事業：中央供電',
    'Electrical Products': '電氣產品',
    'Electronic Components': '電子零組件',
    'Engineering & Construction': '工程與營造',
    'Farming/Seeds/Milling': '農業、種子與磨粉',
    'Finance/Investors Services': '金融與投資人服務',
    'Finance Companies': '金融公司',
    'Finance: Consumer Services': '金融：消費者服務',
    'Fluid Controls': '流體控制',
    'Food Chains': '連鎖食品零售',
    'Home Furnishings': '居家用品',
    'Homebuilding': '住宅建築',
    'Hospital/Nursing Management': '醫院與護理管理',
    'Hotels/Resorts': '飯店與度假村',
    'Industrial Machinery/Components': '工業機械與零組件',
    'Industrial Specialties': '工業專用品',
    'Integrated Freight & Logistics': '綜合貨運與物流',
    'Integrated oil Companies': '綜合石油公司',
    'Investment Managers': '投資管理',
    'Investment Bankers/Brokers/Service': '投資銀行、券商與金融服務',
    'Life Insurance': '人壽保險',
    'Major Banks': '大型銀行',
    'Major Chemicals': '大型化學品',
    'Major Pharmaceuticals': '大型製藥',
    'Marine Transportation': '海運',
    'Meat/Poultry/Fish': '肉類、家禽與魚類',
    'Medicinal Chemicals and Botanical Products': '藥用化學品與植物製品',
    'Medical Specialities': '醫療專科',
    'Medical/Dental Instruments': '醫療與牙科器材',
    'Medical/Nursing Services': '醫療與護理服務',
    'Metal Fabrications': '金屬加工',
    'Military/Government/Technical': '軍事、政府與技術服務',
    'Mining & Quarrying of Nonmetallic Minerals (No Fuels)': '非金屬礦物採礦與採石（非燃料）',
    'Misc Health and Biotechnology Services': '其他健康與生物科技服務',
    'Natural Gas Distribution': '天然氣配送',
    'Newspapers/Magazines': '報紙與雜誌',
    'Office Equipment/Supplies/Services': '辦公設備、用品與服務',
    'Oil & Gas Production': '油氣生產',
    'Oil and Gas Field Machinery': '油氣田機械',
    'Oil/Gas Transmission': '油氣輸送',
    'Oilfield Services/Equipment': '油田服務與設備',
    'Other Consumer Services': '其他消費者服務',
    'Other Specialty Stores': '其他專門零售店',
    'Package Goods/Cosmetics': '包裝商品與化妝品',
    'Packaged Foods': '包裝食品',
    'Pollution Control Equipment': '污染控制設備',
    'Power Generation': '發電',
    'Precision Instruments': '精密儀器',
    'Professional Services': '專業服務',
    'Property-Casualty Insurers': '產險',
    'Radio And Television Broadcasting And Communications Equipment': '廣播電視與通訊設備',
    'Railroads': '鐵路',
    'Real Estate': '不動產',
    'Real Estate Investment Trusts': '不動產投資信託',
    'Recreational Games/Products/Toys': '休閒遊戲、產品與玩具',
    'Restaurants': '餐飲',
    'RETAIL': '零售',
    'Retail-Auto Dealers and Gas Stations': '汽車經銷與加油站零售',
    'Retail: Computer Software & Peripheral Equipment': '零售：電腦軟體與周邊設備',
    'Savings Institutions': '儲蓄金融機構',
    'Semiconductors': '半導體',
    'Services-Misc. Amusement & Recreation': '服務：其他娛樂與休閒',
    'Shoe Manufacturing': '鞋類製造',
    'Specialty Insurers': '專業保險',
    'Specialty Chemicals': '特用化學品',
    'Steel/Iron Ore': '鋼鐵與鐵礦砂',
    'Telecommunications Equipment': '電信設備',
    'Textiles': '紡織',
    'Transportation Services': '運輸服務',
    'Trucking Freight/Courier Services': '卡車貨運與快遞服務',
    'Water Sewer Pipeline Comm & Power Line Construction': '水務、污水、管線、通訊與電力線工程',
}

def translate_sector(value):
    return SECTOR_ZH.get(value, value)

def translate_industry(value):
    if not value:
        return ''
    if value in INDUSTRY_ZH:
        return INDUSTRY_ZH[value]
    parts = [part.strip() for part in value.split(':')]
    translated = [INDUSTRY_ZH.get(part, part) for part in parts if part]
    return '：'.join(translated) if translated else value

def get_stock_note(symbol, code, sector):
    note = (
        stock_notes.get(symbol)
        or stock_notes.get(code)
        or business_map.get(symbol)
        or business_map.get(code)
    )
    if note:
        return str(note)
    if stock_concepts.get(symbol) or stock_concepts.get(code):
        return ''
    industry = industry_map.get(symbol) or industry_map.get(code)
    country = country_map.get(symbol) or country_map.get(code)
    meta = []
    if sector:
        meta.append(f"產業類別：{translate_sector(sector)}")
    if industry:
        meta.append(f"細分產業：{translate_industry(industry)}")
    if country:
        meta.append(f"國家：{country}")
    return " ｜ ".join(meta)

def get_stock_concepts(symbol, code):
    concepts = stock_concepts.get(symbol) or stock_concepts.get(code) or []
    if isinstance(concepts, str):
        concepts = [concepts]
    return [str(item).strip() for item in concepts if str(item).strip()]

def get_theme_strength(symbol, code):
    try:
        return float(stock_theme_strength.get(symbol, stock_theme_strength.get(code, 0)) or 0)
    except (TypeError, ValueError):
        return 0

def get_selected_theme_slug():
    try:
        raw_theme = st.query_params.get('theme')
    except AttributeError:
        raw_theme = st.experimental_get_query_params().get('theme')

    if isinstance(raw_theme, list):
        raw_theme = raw_theme[0] if raw_theme else ''
    return unquote(raw_theme or '')

def build_theme_stats(symbols):
    stats = {}
    for symbol in symbols:
        seen = set()
        for detail in stock_theme_details.get(symbol, []):
            slug = str(detail.get('slug') or detail.get('name') or '').strip()
            if not slug or slug in seen:
                continue
            seen.add(slug)
            name = str(detail.get('name') or slug).strip()
            name_en = str(detail.get('name_en') or '').strip()
            try:
                strength = float(detail.get('avg_change_pct'))
            except (TypeError, ValueError):
                strength = 0.0
            item = stats.setdefault(slug, {
                'slug': slug,
                'name': name,
                'name_en': name_en,
                'strength': strength,
                'count': 0,
            })
            item['count'] += 1
            item['strength'] = strength
    return stats

# 篩選列
filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    type_options = {'全部': None, '漲後整理（型態A）': 'A', '多頭排列（型態B）': 'B'}
    selected_label = st.selectbox('型態選擇', list(type_options.keys()), index=0)
    selected_type = type_options[selected_label]

with filter_col2:
    all_sectors = sorted({v for v in sector_map.values() if v})
    sector_options = ['全部產業'] + all_sectors
    selected_sector = st.selectbox('產業類別', sector_options, index=0)

if selected_type:
    filtered = {k: v for k, v in all_results.items() if v.get('type') == selected_type}
else:
    filtered = all_results

if selected_sector != '全部產業':
    filtered = {k: v for k, v in filtered.items() if v.get('sector') == selected_sector}

base_filtered = filtered
selected_theme_slug = get_selected_theme_slug()
theme_stats = build_theme_stats(base_filtered.keys())

strong_themes = sorted(
    theme_stats.values(),
    key=lambda item: (item['strength'], item['count'], item['name']),
    reverse=True,
)[:5]
weak_themes = sorted(
    theme_stats.values(),
    key=lambda item: (item['strength'], -item['count'], item['name']),
)[:5]

def render_theme_blocks(title, items, css_class):
    blocks = []
    for item in items:
        active_class = ' active' if item['slug'] == selected_theme_slug else ''
        href = f"?theme={quote(item['slug'])}&page=1"
        blocks.append(
            f'<a class="theme-block {css_class}{active_class}" href="{href}">'
            f'<span class="theme-block-name">{html.escape(item["name"])}</span>'
            f'<span class="theme-block-meta"><strong>{item["strength"]:+.2f}%</strong><br>{item["count"]} 檔</span>'
            '</a>'
        )
    st.markdown(
        f'<div><div class="theme-panel-title">{html.escape(title)}</div>'
        f'<div class="theme-block-grid">{"".join(blocks)}</div></div>',
        unsafe_allow_html=True,
    )

if theme_stats:
    strong_col, weak_col = st.columns(2)
    with strong_col:
        render_theme_blocks('最強前五主題', strong_themes, 'theme-strong')
    with weak_col:
        render_theme_blocks('最弱後五主題', weak_themes, 'theme-weak')

selected_theme_name = theme_stats.get(selected_theme_slug, {}).get('name', '')
if selected_theme_slug:
    st.markdown(
        f'<div class="theme-selected-bar">目前主題：{html.escape(selected_theme_name or selected_theme_slug)}'
        f' ｜ <a href="?page=1">清除主題</a></div>',
        unsafe_allow_html=True,
    )
    filtered = {
        k: v for k, v in base_filtered.items()
        if any(detail.get('slug') == selected_theme_slug for detail in stock_theme_details.get(k, []))
    }

symbol_list = sorted(list(filtered.keys()))

if not symbol_list:
    st.info("本次分析未發現符合條件的標的。")
    st.stop()

all_results = filtered

# ==========================================
# 4. 收藏狀態初始化
# ==========================================
if 'selected' not in st.session_state:
    st.session_state.selected = set()

def sync_selected_from_checkboxes():
    selected = set(st.session_state.selected)
    prefix = 'chk_'
    for key, checked in st.session_state.items():
        if not key.startswith(prefix):
            continue
        sym = key[len(prefix):]
        if checked:
            selected.add(sym)
        else:
            selected.discard(sym)
    st.session_state.selected = selected

def toggle_selected(sym):
    if st.session_state.get(f'chk_{sym}', False):
        st.session_state.selected.add(sym)
    else:
        st.session_state.selected.discard(sym)

# ==========================================
# 5. 分頁設定
# ==========================================
PAGE_SIZE = 40
total = len(symbol_list)
total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

def get_query_page():
    try:
        raw_page = st.query_params.get('page')
    except AttributeError:
        raw_page = st.experimental_get_query_params().get('page')

    if isinstance(raw_page, list):
        raw_page = raw_page[0] if raw_page else None

    try:
        return int(raw_page)
    except (TypeError, ValueError):
        return None

def set_query_page(page_number):
    try:
        st.query_params['page'] = str(page_number)
    except AttributeError:
        st.experimental_set_query_params(page=page_number)

if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

query_page = get_query_page()
if query_page is not None:
    st.session_state.current_page = query_page

st.session_state.current_page = max(1, min(st.session_state.current_page, total_pages))

col_info, col_page = st.columns([3, 1])
with col_page:
    page = st.selectbox('頁碼', list(range(1, total_pages + 1)),
                        index=st.session_state.current_page - 1,
                        label_visibility='collapsed')
    st.session_state.current_page = page
    if page != query_page:
        set_query_page(page)
with col_info:
    st.markdown(f"<div style='font-size:0.9rem; color:#000; padding-top:6px;'>共 {total} 檔，第 {page}/{total_pages} 頁</div>", unsafe_allow_html=True)

start = (page - 1) * PAGE_SIZE
page_symbols = symbol_list[start:start + PAGE_SIZE]
sync_selected_from_checkboxes()

# 收藏下載列
sel_count = len(st.session_state.selected)
dl_col, clr_col, _ = st.columns([2, 1, 4])
with dl_col:
    if sel_count > 0:
        tv_text = ','.join(
            s for s in sorted(st.session_state.selected)
        )
        st.download_button(
            f'⬇ 下載收藏清單（{sel_count} 檔）',
            data=tv_text,
            file_name='watchlist.txt',
            mime='text/plain'
        )
    else:
        st.markdown("<div style='padding-top:8px; font-size:0.85rem; color:#888;'>尚未勾選任何標的</div>", unsafe_allow_html=True)
with clr_col:
    if sel_count > 0 and st.button('清除全部'):
        st.session_state.selected = set()
        st.rerun()

# ==========================================
# 6. 繪圖渲染（雙欄極致看板模式）
# ==========================================
for i, sym in enumerate(page_symbols):
    try:
        k_data = all_results[sym]
        plot_df = pd.DataFrame(k_data)

        if plot_df.empty:
            continue

        # 均線由後端預計算，直接使用
        plot_df['MA10'] = plot_df.get('ma10')
        plot_df['MA20'] = plot_df.get('ma20')
        plot_df['MA60'] = plot_df.get('ma60')

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.8, 0.2], vertical_spacing=0.03)

        # K線
        fig.add_trace(go.Candlestick(
            x=plot_df['date'], open=plot_df['open'], high=plot_df['high'],
            low=plot_df['low'], close=plot_df['close'],
            increasing_line_color='#E32636', decreasing_line_color='#008F39',
            increasing_fillcolor='#E32636', decreasing_fillcolor='#008F39',
            increasing_line_width=0.7, decreasing_line_width=0.7,
            name='K線'
        ), row=1, col=1)

        # 均線
        fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['MA10'],
                                 line=dict(color='#f6c23e', width=1), name='10MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['MA20'],
                                 line=dict(color='#8e44ad', width=1), name='20MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['MA60'],
                                 line=dict(color='#36b9cc', width=1), name='60MA'), row=1, col=1)

        # 成交量
        v_colors = ['#ef5350' if c >= o else '#26a69a'
                    for c, o in zip(plot_df['close'], plot_df['open'])]
        fig.add_trace(go.Bar(x=plot_df['date'], y=plot_df['volume'],
                             marker_color=v_colors, name='量'), row=2, col=1)

        fig.update_layout(
            height=350,
            margin=dict(l=5, r=40, t=8, b=20),
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            paper_bgcolor='white',
            plot_bgcolor='white',
            font=dict(color='black'),
            showlegend=False,
            dragmode=False,
            hovermode=False
        )

        fig.update_xaxes(type='category', nticks=10, showgrid=False, zeroline=False,
                         fixedrange=True, tickfont=dict(color='black', size=12), row=1, col=1)
        fig.update_xaxes(type='category', nticks=10, showgrid=False, zeroline=False,
                         fixedrange=True, tickfont=dict(color='black', size=11), row=2, col=1)
        fig.update_yaxes(showgrid=False, zeroline=False, fixedrange=True,
                         tickfont=dict(color='black', size=12), side='right', row=1, col=1)
        fig.update_yaxes(showgrid=False, zeroline=False, fixedrange=True,
                         showticklabels=False, row=2, col=1)

        if i % 2 == 0:
            cols = st.columns(2)

        code = sym
        sector = k_data.get('sector', '')
        industry = k_data.get('industry', '')
        stock_name = name_map.get(sym, '').rstrip('*')
        stock_note = get_stock_note(sym, code, sector)
        concepts = get_stock_concepts(sym, code)
        tooltip_lines = []
        if stock_note:
            tooltip_lines.append(stock_note)
        if concepts:
            tooltip_lines.append(f"市場主題：{'、'.join(concepts)}")
        if sector and not any(line.startswith('產業類別：') for line in tooltip_lines):
            tooltip_lines.append(f"產業類別：{translate_sector(sector)}")
        if industry and not any('細分產業：' in line for line in tooltip_lines):
            tooltip_lines.append(f"細分產業：{translate_industry(industry)}")
        stock_note_html = html.escape('\n'.join(tooltip_lines) or '暫無產業/主題資料').replace('\n', '<br>')
        title_text = (
            f"{code} {stock_name}"
            f" {'｜漲後整理' if k_data.get('type')=='A' else '｜多頭排列'}"
            f"{f'  [{sector}]' if sector else ''}"
            f"{'  RS↑' if k_data.get('rs_spy') else ''}"
            f"{'  VOL↑' if k_data.get('vol_surge') else ''}"
            f"{'  Theme↑' if get_theme_strength(sym, code) > 0 else ''}"
        )
        title_html = (
            '<span class="stock-title">'
            f'{html.escape(title_text)}'
            f'<span class="stock-tooltip">{stock_note_html}</span>'
            '</span>'
        )

        with cols[i % 2]:
            chk_col, title_col = st.columns([0.05, 0.95])
            with chk_col:
                checked = st.checkbox('', value=sym in st.session_state.selected,
                                      key=f"chk_{sym}", label_visibility='collapsed',
                                      on_change=toggle_selected, args=(sym,))
            with title_col:
                st.markdown(title_html, unsafe_allow_html=True)

            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"fig_{page}_{sym}",
                theme=None,
                config={
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': f'{sym}_Analysis',
                        'scale': 2
                    },
                    'staticPlot': True,
                    'displayModeBar': False
                }
            )
            st.markdown("<br>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"渲染 {sym} 時發生錯誤: {e}")
        continue

st.markdown("---")

# 底部分頁導覽
def get_page_range(current, total):
    if total <= 9:
        return list(range(1, total + 1))
    pages = set([1, total])
    for p in range(max(1, current - 2), min(total, current + 2) + 1):
        pages.add(p)
    result, prev = [], None
    for p in sorted(pages):
        if prev and p - prev > 1:
            result.append('...')
        result.append(p)
        prev = p
    return result

page_range = get_page_range(page, total_pages)

# 底部右對齊導覽：純文字連結，target=_self 保持在同一個視窗切換
nav_items = []
if page > 1:
    nav_items.append(f'<a href="?page={page - 1}" target="_self">◀ 前一頁</a>')
else:
    nav_items.append('<span class="disabled-page">◀ 前一頁</span>')

for p in page_range:
    if p == '...':
        nav_items.append('<span>…</span>')
    elif p == page:
        nav_items.append(f'<span class="current-page">{p}</span>')
    else:
        nav_items.append(f'<a href="?page={p}" target="_self">{p}</a>')

if page < total_pages:
    nav_items.append(f'<a href="?page={page + 1}" target="_self">下一頁 ▶</a>')
else:
    nav_items.append('<span class="disabled-page">下一頁 ▶</span>')

st.markdown(
    f'<nav class="pagination-nav">{"".join(nav_items)}</nav>',
    unsafe_allow_html=True
)

st.markdown("<br>", unsafe_allow_html=True)
