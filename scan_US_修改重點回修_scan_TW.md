# scan_US 修改重點與回修 scan_TW Checklist

這份文件整理本次 `scan_US` 相對原本 `scan-TW` 的主要修改，方便後續回頭修正 `scan-TW` 時參照。

## 資料更新

- 下載資料改為美股 universe：Nasdaq screener。
- 排除非普通股：ADR / ADS、ETF、基金、權證、特別股、信託、債券、unit、right、index 等。
- 價格資料使用 Yahoo Finance / `yfinance`。
- 增加 `SPY` 作為 RS 相對強弱基準。
- `uptrend_results.json` 增加或保留：
  - `sector_map`
  - `industry_map`
  - `country_map`
  - `business_map`
  - `rs_spy`
  - `vol_surge`

## USStockFlow 主題

- 新增抓取 `https://usstockflow.aihost.dev/` API。
- `stock_concepts.json` 改成包含：
  - 標的對應主題
  - 主題強度
  - 主題明細
  - 全市場主題排名 `market_theme_rankings`
- 「今日領漲族群 / 今日領跌族群」直接用 USStockFlow 全市場前五/後五。
- 點選主題區塊後，只顯示該主題與本專案掃出標的的交集。

## UI 篩選

- 保留原本「型態選擇」。
- 產業篩選改回只有「產業類別」下拉。
- 市場主題不再用下拉，改成 block 卡片顯示：
  - 今日領漲族群
  - 今日領跌族群
- block 上顯示主題漲跌幅與本專案篩出的交集數量。

## 標的顯示

- 標的後方新增標記：
  - `RS↑`：近 60 日報酬率高於 SPY。
  - `VOL↑`：近 5 日均量大於等於近 20 日均量 1.6 倍。
  - `Theme↑`：有 USStockFlow 主題且主題強度大於 0。
- 滑鼠 hover 註解改成中文，包含：
  - 市場主題
  - 產業類別
  - 細分產業
  - 國家 / business note

## 收藏清單

- 修正跨頁勾選會消失的問題。
- 勾選狀態同步到 URL `selected` query param。
- 底部分頁、上一頁、下一頁、主題 block、清除主題都會保留 `selected`。
- 不論在哪一頁，都可以下載目前累積收藏清單。

## TradingView 匯出

- 原本匯出單純 `AAPL,MSFT,NVDA`。
- 改成依細分產業分組：

```txt
###Semiconductors###
AAOI,NVDA,AMD

###Aluminum###
AA
```

- 分類標題已拿掉「標的」兩字。

## 文件與腳本

- `update_and_open.bat` / `update_and_open.sh` 更新：
  - 檢查 venv 是否存在。
  - 檢查 Streamlit 是否安裝。
  - 更新資料後自動 `git add` / `commit` / `push`。
  - 若沒有資料變更，不再誤判為錯誤。
- `安裝說明.md` 重寫：
  - 資料來源
  - 排除規則
  - USStockFlow 主題
  - 跨頁收藏
  - TradingView 匯出格式
- `篩股邏輯.md` 重寫：
  - 型態 A/B
  - 波段條件
  - RS/VOL
  - 資料來源
  - 主題與匯出說明
- `.devcontainer/devcontainer.json` 修正為開啟實際存在的說明檔。
- `stock_notes.example.json` 改成正常中文範例。

## 回修 scan_TW 建議順序

1. 先修「跨頁收藏累積」與 TradingView 分組匯出，這是最通用、最直接有感的功能。
2. 再修文件與 `update_and_open`，避免使用者執行時誤判錯誤。
3. 最後再評估是否要把「市場主題 block」概念搬回台股版，因為台股版資料來源可能不一定能完全對應 USStockFlow。

