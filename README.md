# 🚀 AI 量化戰情室 - 台股分析系統

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

即時台股分析與量化選股工具，讓投資決策更科學。

## ✨ 主要功能

### 📊 核心模組
- **🚀 全自動量化選股** - 動態類股掃描、多策略篩選
- **🏆 台灣50分析** - 排除金融股的成分股追蹤
- **📈 MA5突破MA20掃描** - 短線技術訊號篩選
- **💼 持倉管理** - 記錄買賣、自動計算損益
- **⭐ 觀察清單** - 追蹤感興趣的投資標的
- **🔍 個股深度體檢** - 技術面 + 籌碼面完整分析

### 📈 技術指標
- K 線圖（紅漲綠跌，符合台股習慣）
- 移動平均線（MA5/20/60）
- RSI 相對強弱指標、MACD、KDJ
- 成交量分析
- 外資/投信買賣超（需 FinMind）

## 📦 本地安裝

```bash
git clone https://github.com/ykdaniel/stock-analyzer.git
cd stock-analyzer
pip install -r requirements.txt
streamlit run app.py
```

瀏覽器預設會開啟 http://localhost:8501

## 🌐 如何上線（部署到 Streamlit Community Cloud）

**免費、官方推薦方式：**

1. **登入**  
   前往 [https://share.streamlit.io](https://share.streamlit.io)，用 **GitHub 帳號**登入。

2. **New app**  
   點「New app」。

3. **選擇倉庫**  
   - **Repository**：選 `ykdaniel/stock-analyzer`（或你的 GitHub 帳號/倉庫名）  
   - **Branch**：`main`  
   - **Main file path**：`app.py`

4. **Advanced settings（可選）**  
   若需要 Python 3.11：  
   - 展開 Advanced settings  
   - Python version 選 3.11

5. **Deploy**  
   點「Deploy」，等幾分鐘建置完成。

6. **取得網址**  
   完成後會得到一個網址，例如：  
   `https://stock-analyzer-xxxxx.streamlit.app`  
   之後用這個網址就能從任何地方開啟你的程式。

**注意：**
- 觀察清單、持股、歷史會存在雲端 session，關閉瀏覽器後可能清空；若要持久化需另接資料庫或雲端儲存。
- yfinance / FinMind 在雲端一樣可用，但受網路與 API 限制。

## 📚 使用說明

1. **個股分析**：進入「🔍 單一個股體檢」，輸入代號（如 2330.TW）。
2. **量化選股**：進入「🚀 全自動量化選股」，選擇類股後啟動掃描。
3. **持倉管理**：在「📦 我持有的股票診斷」記錄買賣與損益。

台股代號請加 `.TW` 後綴（例如 2330.TW）。

## 🐛 已知限制

- 資料依賴 Yahoo Finance、FinMind，免費版有延遲與限制。
- 首次載入較慢，建議單次掃描不超過 50 檔。

## ⚠️ 免責聲明

本系統僅供教育與研究用途，不構成投資建議。投資有風險，請謹慎評估。

---

Made with ❤️ using Streamlit
