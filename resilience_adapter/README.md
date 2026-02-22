# Resilience Adapter 使用指南

這是一個為了與不穩定 AI Web UI (如 ChatGPT, Gemini) 互動而設計的中介層系統。它不包含瀏覽器驅動本身，而是透過 `BrowserDriverInterface` 連接到您現有的瀏覽器。

## 1. 環境準備

### 安裝依賴
```bash
pip install playwright
playwright install chromium
```

### 啟動瀏覽器 (Chrome)
為了讓程式接管您的瀏覽器 Session (保留登入狀態)，請從終端機使用 debugging port 啟動 Chrome：

**Windows:**
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\YUKAI\ChromeDevSession"
```
*(請確保所有其他 Chrome 視窗已關閉，或使用不同的 user-data-dir)*

## 2. 執行範例

我們提供了一個範例腳本，演示如何連接到上述開啟的 Chrome 並發送訊息。

```bash
python c:\Users\YUKAI\Desktop\MyStockApp\resilience_adapter\examples\connect_real_browser.py
```

## 3. 核心概念

### Selector Trust Tiers (選擇器信任階級)
在 `SelectorDefinition` 中定義多個選擇器。系統會優先嘗試 `tier_index=0`，失敗則退化到 `tier_index=1` 並記錄警告。

### Behavioral Entropy (行為熵)
系統會自動模擬人類打字行為（不規則延遲、分段打字），您不需要手動撰寫 `time.sleep`。

### Structural Anchor (結構錨點)
系統驗證回覆是否緊接在您的最後一條訊息之後，避免抓取到歷史對話。

## 4. 自定義整合

若您使用其他自動化工具 (如 Selenium)，請參考 `core/interfaces.py` 實作 `BrowserDriverInterface`，然後注入到 `ResilienceController` 中即可。
