# W11 作業：股票 LINE Bot

> **繳交方式**：將你的 GitHub repo 網址貼到作業繳交區
> **作業性質**：個人作業

---

## 作業目標

利用上週設計的 Skill，開發一個股票相關的 LINE Bot。
重點不是功能多寡，而是你設計的 **Skill 品質**——Skill 寫得越具體，AI 產出的程式碼就越接近可以直接執行。

---

## 功能要求（擇一實作）

| 功能         | 說明                              |
| ------------ | --------------------------------- |
| AI 分析股票  | 使用者說股票名稱，Gemini 給出分析 |
| 追蹤清單     | 儲存使用者的自選股清單到 SQLite   |
| 查詢即時價格 | 整合 yfinance 或 twstock 取得股價 |

> 以「可以執行、能回覆訊息」為目標，不需要複雜

---

## 繳交項目

你的 GitHub repo 需要包含：

| 項目                   | 說明                                  |
| ---------------------- | ------------------------------------- |
| `app.py`               | LINE Webhook + Gemini + SQLite 後端   |
| `requirements.txt`     | 所有套件                              |
| `.env.example`         | 環境變數範本（不含真實 token）        |
| `.agents/skills/`      | 至少包含 `/linebot-implement` Skill   |
| `README.md`            | 本檔案（含心得報告）                  |
| `screenshots/chat.png` | LINE Bot 對話截圖（至少一輪完整對話） |

### Skill 要求

`.agents/skills/` 至少需要包含：

- `/linebot-implement`：產出 LINE Bot 主程式（必要）
- `/prd` 或 `/architecture`：延用上週的
- `/commit`：延用上週的

---

## 專案結構

```
your-repo/
├── .agents/
│   └── skills/
│       ├── prd/SKILL.md
│       ├── linebot-implement/SKILL.md
│       └── commit/SKILL.md
├── docs/
│   └── PRD.md
├── screenshots/
│   └── chat.png
├── app.py
├── requirements.txt
├── .env.example
└── README.md
```

> `.env` 和 `users.db` 不要 commit（加入 `.gitignore`）

---

## LINE Console 設定（第一次跑前要做）

1. 到 [LINE Developers Console](https://developers.line.biz/) 登入並建立 Provider
2. 在 Provider 內 **Create a Messaging API channel**
3. 建好 channel 後到 **LINE Official Account Manager → 回應設定**：
   - **關閉「自動回應訊息」**（否則 LINE 會搶在你的程式之前回預設文字）
   - 啟用 **Webhook**
4. 回到 LINE Developers Console → 你的 channel：
   - **Basic settings** 取 `Channel secret`
   - **Messaging API** 取 `Channel access token`（長效版，點「Issue」產生）
5. 申請 Gemini API key：[Google AI Studio](https://aistudio.google.com/app/apikey)

---

## 指令一覽

| 在 LINE 傳這個 | 會收到                    |
| -------------- | ------------------------- |
| `選單`         | 指令說明                  |
| `查詢 2330`    | 台積電即時報價（twstock） |
| `分析 台積電`  | Gemini 給的簡短分析       |
| `追蹤 2330`    | 加入你的自選股            |
| `清單`         | 列出你的自選股            |
| `刪除 2330`    | 從自選股移除              |

---

## 啟動方式

```bash
# 1. 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. 安裝套件
pip install -r requirements.txt

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env，填入三個 token

# 4. 啟動 FastAPI
python -m uvicorn app:app --reload --port 7777

# 5. 另開終端機啟動 ngrok
ngrok http 7777
# 複製 https 網址，填入 LINE Developers Console 的 Webhook URL（加上 /callback）
# 點「Verify」確認連線正常後，掃 QR Code 加好友開始測試
```

---

## 心得報告

**姓名**：曹世杰
**學號**：D1149576

**Q1. 你在 `/linebot-implement` Skill 的「注意事項」寫了哪些規則？為什麼這樣寫？**

> 主要寫了四類規則：(1) 強制使用 line-bot-sdk v3，並附 v2/v3 對照表，避免 AI 退化到舊寫法；(2) token 一律從 `os.getenv` 讀，啟動時缺值就 raise，避免被 commit 到 repo；(3) Webhook 不論成功失敗都回 200（簽章錯例外），避免 LINE 重試風暴；(4) replyToken 只能用一次。會這樣寫是因為這些是 LINE Bot 最容易踩、又不會在 Python 語法層被擋下來的錯。

---

**Q2. 你的 Skill 第一次執行後，AI 產出的程式直接能跑嗎？需要修改哪些地方？修改後有沒有更新 Skill？**

> 大致能跑，但實際測試遇到兩個小問題：(1) 使用者習慣傳「查詢2330」沒空格，原本只切 partition 切不出來，後來改寫了 `split_command` 支援無空格情況；(2) Gemini 模型名稱原本寫死 `gemini-2.0-flash`，但 API key 對該模型沒配額，改成可由 `GEMINI_MODEL` 環境變數覆寫，預設 `gemini-2.5-flash-lite`。第二點之後可以回頭把「模型名要做成可配置」寫進 Skill。

---

**Q3. 你遇到什麼問題是 AI 沒辦法自己解決、需要你介入處理的？**

> 環境問題 AI 看不到：第一次跑 uvicorn 時 ModuleNotFoundError，因為我沒有 activate venv，AI 從錯誤訊息看不出來這是環境問題還是程式問題。另外 LINE Console 那邊的「自動回應訊息」要關、Webhook URL 結尾要加 `/callback`、ngrok 重啟網址會變，這些只能我自己去 Console 操作，AI 沒辦法代勞。

---

**Q4. 如果你要把這個 LINE Bot 讓朋友使用，你還需要做什麼？**

> 至少三件事：(1) 部署到雲端（Render / Railway / Fly.io），不能再靠本機 + ngrok；(2) Gemini 與 LINE token 改用平台的 secret 管理，不放 `.env`；(3) SQLite 換成可持久化的 volume 或改用 Postgres，避免容器重啟資料消失。再進階的話會加上速率限制、錯誤監控（Sentry）、以及把 Gemini 推論改成背景任務 + push message，避免使用者等太久。
