---
name: linebot-implement
description: 產出可直接執行的股票 LINE Bot 程式碼(FastAPI + line-bot-sdk v3 + Gemini + SQLite + twstock)。輸入需求或 PRD,產出 app.py、requirements.txt、.env.example。
---

# /linebot-implement

把股票 LINE Bot 的需求轉成**可以直接 `uvicorn app:app --reload` 跑起來**的單檔實作。

---

## 你要做什麼(任務)

產出 **三個檔案**,放在專案根目錄:

| 檔名 | 內容 |
|---|---|
| `app.py` | FastAPI + line-bot-sdk v3 + Gemini + SQLite + twstock 的單檔實作 |
| `requirements.txt` | 鎖好版本範圍的相依清單 |
| `.env.example` | 三個 key 的範本(不含真實 token) |

`app.py` 必須處理三類使用者輸入:

| 使用者傳的訊息 | 行為 |
|---|---|
| `分析 <股票名或代號>` | 呼叫 Gemini,回投資面向分析(基本面/題材/風險) |
| `查詢 <股號>` | 用 `twstock.realtime.get()` 取即時報價,格式化回覆 |
| `追蹤 <股號>` | 加入該使用者的 watchlist (SQLite) |
| `清單` | 列出該使用者目前追蹤的股號 |
| `刪除 <股號>` | 從 watchlist 移除 |
| 其他文字 | 回說明選單 |

每筆訊息與回覆都要寫進 `interactions` 表(教材要求「記錄 userId 與互動紀錄」)。

---

## 你不能做什麼(限制)

### SDK 版本
- **必須使用 line-bot-sdk-python v3**,import 一律走 `linebot.v3.*`
- **禁止** `from linebot import LineBotApi`(這是 v2)
- **禁止** `from linebot.models import TextSendMessage`(這是 v2)
- 在 `requirements.txt` 鎖 `line-bot-sdk>=3.11,<4`

### 安全
- **禁止把 token 寫死在程式碼**,只能用 `os.getenv("LINE_CHANNEL_ACCESS_TOKEN")` 等
- 啟動時三個環境變數任一缺失,就 `raise RuntimeError`,不要靜默 fallback
- 簽章驗證**必須走 `WebhookHandler.handle()`**,不要自己寫 HMAC
- 收到 `InvalidSignatureError` 要回 HTTP 400,不是 500

### Webhook 行為
- `/callback` 必須**永遠在 30 秒內回 200**(LINE 會重試)
- 任何例外都要被捕捉,**不能**讓 FastAPI 回 500
- `replyToken` **只能用一次**:呼叫過 `reply_message_with_http_info` 之後,同個 token 不能再 reply,要追加訊息得用 push API

### 效能
- **禁止引入** `pandas`、`numpy`、`yfinance` 除非有強理由(twstock 已內建即時報價)
- SQLite 連線要 `check_same_thread=False`(FastAPI 多 thread)或每次新開連線
- Gemini 回應若 > 4900 字元,**截斷到 4900**(LINE 上限 5000)

---

## 怎麼收尾(輸出規格)

### 啟動指令(README 必須這樣寫)
```bash
uvicorn app:app --reload --port 8000
```

### Webhook endpoint
- 路徑固定:`POST /callback`
- 健康檢查:`GET /` 回 `{"status": "ok"}`(方便瀏覽器測 ngrok)

### 環境變數(`.env.example` 必含這三個 key)
```
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
GEMINI_API_KEY=
```

### SQLite schema(啟動時 `CREATE TABLE IF NOT EXISTS`)
```sql
CREATE TABLE IF NOT EXISTS users (
  user_id   TEXT PRIMARY KEY,
  joined_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
  user_id  TEXT NOT NULL,
  stock_id TEXT NOT NULL,
  added_at TEXT NOT NULL,
  PRIMARY KEY (user_id, stock_id)
);

CREATE TABLE IF NOT EXISTS interactions (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  message TEXT NOT NULL,
  reply   TEXT NOT NULL,
  ts      TEXT NOT NULL
);
```

DB 檔名固定 `users.db`,放專案根目錄。

---

## 開發前 checklist(產出程式前自己先過一遍)

- [ ] 我用的是 line-bot-sdk **v3**(import 是 `linebot.v3.*`)
- [ ] 三個環境變數**都讀 `os.getenv`**,沒有 hardcode
- [ ] Webhook 處理函式**不論成功失敗都回 200**(除了簽章錯誤回 400)
- [ ] `replyToken` 只用一次
- [ ] SQLite 在程式啟動時建表,且 `.env` 與 `users.db` 在 `.gitignore`
- [ ] LINE Console 端的「自動回應訊息」要在 README 提醒使用者**關掉**

---

## v2 → v3 對照表(教材重點,寫死在這以防 AI 退化到 v2)

| 用途 | v2(❌ 禁用) | v3(✅ 用這個) |
|---|---|---|
| import handler | `from linebot import WebhookHandler` | `from linebot.v3 import WebhookHandler` |
| import client | `from linebot import LineBotApi` | `from linebot.v3.messaging import Configuration, ApiClient, MessagingApi` |
| import event | `from linebot.models import MessageEvent, TextMessage` | `from linebot.v3.webhooks import MessageEvent, TextMessageContent` |
| import 訊息物件 | `from linebot.models import TextSendMessage` | `from linebot.v3.messaging import ReplyMessageRequest, TextMessage` |
| import 例外 | `from linebot.exceptions import InvalidSignatureError` | `from linebot.v3.exceptions import InvalidSignatureError` |
| reply 寫法 | `line_bot_api.reply_message(token, TextSendMessage(text=...))` | `with ApiClient(configuration) as api_client:`<br>`    MessagingApi(api_client).reply_message_with_http_info(`<br>`        ReplyMessageRequest(reply_token=token, messages=[TextMessage(text=...)]))` |

---

## 標準 Webhook 骨架(照抄即可)

```python
import os
from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET 未設定")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
app = FastAPI()

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    reply_text = route(event.source.user_id, event.message.text)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text[:4900])],
            )
        )
```

---

## 常見地雷(產出程式前自查)

| 地雷 | 後果 | 怎麼避免 |
|---|---|---|
| reply token 重複用 | LINE API 回 400 | 一個 event 只 reply 一次,要追加訊息用 push API |
| Webhook 沒回 200 | LINE 重試,使用者重複收到回覆 | 任何例外都吞掉,記 log,但 endpoint 永遠回 200(簽章錯例外) |
| 沒驗簽章 | 任何人能打你的 endpoint 灌訊息 | 一定走 `handler.handle(body, signature)` |
| SQLite 多執行緒衝突 | `SQLite objects created in a thread can only be used in that same thread` | `sqlite3.connect("users.db", check_same_thread=False)` 或每次新建連線 |
| Gemini 回應太長 | LINE API 回 400(訊息超過 5000 字) | reply 前 `text[:4900]` |
| twstock 拿不到資料 | 拋例外讓 webhook 500 | `try/except`,失敗回「查無此股號或服務暫時不穩,請稍後再試」 |
| Gemini 429 | 同上 | 同上,回友善訊息 |
| 把教材檔/.env commit 進 git | 洩漏 token | `.gitignore` 寫 `.env`、`users.db`、`9. FastAPI + LINE Bot/` |

---

## 升級路徑(本作業範圍**外**,但留筆記)

如果 Gemini 推論超過 5 秒讓使用者等不耐煩:
1. 先 `reply_message` 暫存訊息(「分析中,請稍候…」)
2. 用 FastAPI `BackgroundTasks` 跑 Gemini
3. 完成後改用 `push_message` 主動發給該 user_id

但 **本作業先不做**,簡單同步即可。

---

## 自我檢查(對應教材的四個提問)

產出程式後,對自己提問:

1. **AI 知道用哪個版本的 SDK 嗎?** → 是,鎖在 `line-bot-sdk>=3.11,<4`,且 import 路徑強制走 v3
2. **AI 知道 Webhook 一定要回 200 嗎?** → 是,limits 那節寫死了,範例骨架也是這樣
3. **AI 知道 replyToken 只能用一次嗎?** → 是,「常見地雷」第一條
4. **AI 知道 .env 要哪些 key 嗎?** → 是,「環境變數」段列了三個

任一項回答「不確定」,就回頭把這份 SKILL.md 補滿再產出程式。
