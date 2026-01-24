# 🚀 AI 量化戰情室 - 台股分析系統

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

即時台股分析與量化選股工具，讓投資決策更科學。

## ✨ 主要功能

### 📊 核心模組
- **🚀 全自動量化選股** - 動態類股掃描、多策略篩選
- **🏆 台灣50分析** - 排除金融股的成分股追蹤
- **💼 持倉管理** - 記錄買賣、自動計算損益
- **⭐ 觀察清單** - 追蹤感興趣的投資標的
- **🔍 個股深度體檢** - 技術面 + 籌碼面完整分析

### 📈 技術指標
- K 線圖（紅漲綠跌，符合台股習慣）
- 移動平均線（MA5/20/60）
- RSI 相對強弱指標
- MACD 指標
- 成交量分析
- 外資/投信買賣超（需 FinMind）

### 🎯 選股策略
1. **模式 A - 抄底模式**：超賣反彈，適合短線進場
2. **模式 B - 強勢突破**：突破關鍵位，追逐強勢股
3. **模式 C - 穩健追蹤**：波段操作，風險相對較低

## 🛠️ 技術棧

```
Frontend: Streamlit
Data: yfinance + FinMind
Visualization: Plotly
Analysis: Pandas + NumPy
```

## 📦 本地安裝

### 環境需求
- Python 3.7+
- pip

### 安裝步驟

```bash
# 1. Clone repository
git clone https://github.com/你的用戶名/stock-analyzer.git
cd stock-analyzer

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 執行程式
streamlit run stock_FIXED.py

# 4. 開啟瀏覽器
# 預設會自動開啟 http://localhost:8501
```

## 🌐 線上使用

直接訪問我們的線上版本（部署後更新此連結）：
```
https://your-app.streamlit.app
```

## 📚 使用說明

### 快速開始

1. **個股分析**
   - 進入「🔍 單一個股體檢」
   - 輸入股票代號（例如：2330.TW）
   - 查看完整技術分析與籌碼數據

2. **量化選股**
   - 進入「🚀 全自動量化選股」
   - 選擇產業類股
   - 選擇策略模式
   - 系統自動掃描並排序

3. **持倉管理**
   - 記錄買入資訊
   - 自動計算未實現損益
   - 賣出後移至歷史紀錄

### 支援的股票代號格式

- 台股：`2330.TW`、`2454.TW`（加 .TW 後綴）
- 內建 100+ 檔台股資料庫

## 📊 內建資料庫

涵蓋主要類股：
- 🔵 半導體/IC設計（台積電、聯發科等）
- 🟢 記憶體（南亞科、群聯等 15 檔）
- 🟡 AI/電腦週邊（鴻海、廣達等）
- 🟠 傳產/重電（中興電、華城等）
- 🔴 航運（長榮、陽明等）
- 🟣 金融（富邦金、國泰金等）
- ⚪ 電子零組件（台達電、國巨等）

## ⚙️ 配置

### 環境變數（可選）

如果需要使用 FinMind API Token：

創建 `.streamlit/secrets.toml`：
```toml
FINMIND_TOKEN = "your_token_here"
```

### 自訂設定

編輯 `.streamlit/config.toml` 可以調整：
- 主題顏色
- 伺服器設定
- 快取設定

## 🐛 已知限制

1. **資料來源**
   - 依賴 Yahoo Finance API（免費但有延遲）
   - 部分冷門股票資料可能不完整

2. **籌碼功能**
   - 需要安裝 FinMind
   - 免費版有使用限制

3. **效能**
   - 首次載入較慢（需下載資料）
   - 建議不要一次掃描超過 50 檔股票

## 🔧 疑難排解

### 常見問題

**Q: 執行後出現 ModuleNotFoundError？**
```bash
pip install -r requirements.txt
```

**Q: 圖表無法顯示？**
```bash
pip install --upgrade plotly
```

**Q: 資料載入失敗？**
- 檢查網路連線
- 確認股票代號格式正確（需加 .TW）
- Yahoo Finance API 可能暫時無法使用

**Q: FinMind 警告？**
```bash
pip install FinMind  # 安裝後即可使用籌碼功能
```

## 📝 更新日誌

### v1.0 (2026-01-24)
- ✅ 移除重複函數定義
- ✅ 修復語法錯誤
- ✅ 優化程式碼結構
- ✅ 完整錯誤處理

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request！

## 📄 授權

MIT License

## ⚠️ 免責聲明

**本系統僅供教育和研究用途，不構成投資建議。**

- 所有數據來自公開資料源
- 技術指標僅供參考
- 投資有風險，請謹慎評估
- 作者不對使用本系統造成的任何損失負責

## 📞 聯絡方式

- Issues: [GitHub Issues](https://github.com/你的用戶名/stock-analyzer/issues)
- Email: your-email@example.com

## 🌟 Star History

如果這個專案對你有幫助，請給個 Star ⭐

---

Made with ❤️ using Streamlit
