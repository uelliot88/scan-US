import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import html

# ==========================================
# 頁面與底色初始化
# ==========================================
st.set_page_config(page_title="台股掃圖", layout="wide")

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

def load_stock_concepts():
    try:
        with open('stock_concepts.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}

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
        <div style='font-size: 2.2rem; font-weight: 900; color: #000000; line-height: 1.2;'>台股掃圖</div>
        <div style='font-size: 0.9rem; font-weight: 800; color: #000000;'>更新：{last_updated}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 準備渲染資料
# ==========================================
all_results = data_store['results']
name_map = data_store.get('name_map', {})
sector_map = data_store.get('sector_map', {})
business_map = data_store.get('business_map', {})
stock_notes = load_stock_notes()
stock_concepts = load_stock_concepts()

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
    if sector:
        return f"產業別：{sector}"
    return ""

def get_stock_concepts(symbol, code):
    concepts = stock_concepts.get(symbol) or stock_concepts.get(code) or []
    if isinstance(concepts, str):
        concepts = [concepts]
    return [str(item).strip() for item in concepts if str(item).strip()]

# 篩選列
filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    type_options = {'全部': None, '漲後整理（型態A）': 'A', '多頭排列（型態B）': 'B'}
    selected_label = st.selectbox('型態選擇', list(type_options.keys()), index=0)
    selected_type = type_options[selected_label]

with filter_col2:
    all_sectors = sorted({v for v in sector_map.values() if v})
    sector_options = ['全部產業'] + all_sectors
    selected_sector = st.selectbox('產業別', sector_options, index=0)

if selected_type:
    filtered = {k: v for k, v in all_results.items() if v.get('type') == selected_type}
else:
    filtered = all_results

if selected_sector != '全部產業':
    filtered = {k: v for k, v in filtered.items() if v.get('sector') == selected_sector}

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

# 收藏下載列
sel_count = len(st.session_state.selected)
dl_col, clr_col, _ = st.columns([2, 1, 4])
with dl_col:
    if sel_count > 0:
        tv_text = ','.join(
            ('TWSE:' if s.endswith('.TW') else 'TPEX:') + s.replace('.TWO', '').replace('.TW', '')
            for s in sorted(st.session_state.selected)
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

        code = sym.replace('.TWO', '').replace('.TW', '')
        sector = k_data.get('sector', '')
        stock_name = name_map.get(sym, '').rstrip('*')
        stock_note = get_stock_note(sym, code, sector)
        concepts = get_stock_concepts(sym, code)
        tooltip_lines = []
        if stock_note:
            tooltip_lines.append(stock_note)
        if concepts:
            tooltip_lines.append(f"市場主題：{'、'.join(concepts)}")
        if sector and not any(line.startswith('產業別：') for line in tooltip_lines):
            tooltip_lines.append(f"產業別：{sector}")
        stock_note_html = html.escape('\n'.join(tooltip_lines) or '暫無市場主題').replace('\n', '<br>')
        title_text = (
            f"{code} {stock_name}"
            f" {'｜漲後整理' if k_data.get('type')=='A' else '｜多頭排列'}"
            f"{f'  [{sector}]' if sector else ''}"
            f"{'  🔵外資' if k_data.get('inst_foreign') else ''}"
            f"{'  🟢投信' if k_data.get('inst_trust') else ''}"
            f"{'  VOL🔺' if k_data.get('vol_surge') else ''}"
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
                                      key=f"chk_{page}_{sym}", label_visibility='collapsed')
            with title_col:
                st.markdown(title_html, unsafe_allow_html=True)
            if checked:
                st.session_state.selected.add(sym)
            else:
                st.session_state.selected.discard(sym)

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
