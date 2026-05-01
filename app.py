import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

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

    /* 底部分頁導覽：所有換頁控制改成純文字外觀 */
    div:has(.page-nav-start) ~ [data-testid="stHorizontalBlock"]
      > [data-testid="column"]
      button {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        min-height: 0px !important;
        padding: 2px 5px !important;
        font-size: 1rem !important;
        line-height: 1.6 !important;
        cursor: pointer !important;
    }
    div:has(.page-nav-start) ~ [data-testid="stHorizontalBlock"]
      > [data-testid="column"]
      button:hover {
        background: #eeeeee !important;
        border-radius: 3px !important;
    }
    div:has(.page-nav-start) ~ [data-testid="stHorizontalBlock"]
      > [data-testid="column"]
      button:disabled {
        background: transparent !important;
        opacity: 0.45 !important;
        cursor: default !important;
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

if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
st.session_state.current_page = max(1, min(st.session_state.current_page, total_pages))

col_info, col_page = st.columns([3, 1])
with col_page:
    page = st.selectbox('頁碼', list(range(1, total_pages + 1)),
                        index=st.session_state.current_page - 1,
                        label_visibility='collapsed')
    st.session_state.current_page = page
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
        title_label = (
            f"**{code} {name_map.get(sym, '')}"
            f" {'｜漲後整理' if k_data.get('type')=='A' else '｜多頭排列'}"
            f"{f'  [{sector}]' if sector else ''}"
            f"{'  🔵外資' if k_data.get('inst_foreign') else ''}"
            f"{'  🟢投信' if k_data.get('inst_trust') else ''}"
            f"{'  VOL🔺' if k_data.get('vol_surge') else ''}**"
        )

        with cols[i % 2]:
            chk_col, title_col = st.columns([0.05, 0.95])
            with chk_col:
                checked = st.checkbox('', value=sym in st.session_state.selected,
                                      key=f"chk_{page}_{sym}", label_visibility='collapsed')
            with title_col:
                st.markdown(title_label)
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

# 底部右對齊導覽：◀前一頁  1 2 3 … 10  下一頁▶
_, nav_col = st.columns([1, 3])
with nav_col:
    st.markdown('<span class="page-nav-start"></span>', unsafe_allow_html=True)
    nav_widths = [2] + [1] * len(page_range) + [2]
    nav_cols = st.columns(nav_widths)

    with nav_cols[0]:
        if st.button('◀ 前一頁', disabled=(page == 1), key='nav_prev'):
            st.session_state.current_page = page - 1
            st.rerun()

    for idx, p in enumerate(page_range):
        with nav_cols[idx + 1]:
            if p == '...':
                st.markdown("<div style='text-align:center;padding-top:6px'>…</div>", unsafe_allow_html=True)
            elif p == page:
                st.markdown(
                    f"<div style='text-align:center;font-weight:900;text-decoration:underline;padding-top:5px'>{p}</div>",
                    unsafe_allow_html=True
                )
            else:
                if st.button(str(p), key=f'nav_p_{p}'):
                    st.session_state.current_page = p
                    st.rerun()

    with nav_cols[-1]:
        if st.button('下一頁 ▶', disabled=(page == total_pages), key='nav_next'):
            st.session_state.current_page = page + 1
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
