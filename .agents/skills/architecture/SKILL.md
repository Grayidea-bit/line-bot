---
name: architecture
description: 將 PRD 轉成技術架構文件。產出 docs/ARCHITECTURE.md,描述模組、資料流、SQLite schema、外部相依。
---

# /architecture

讀 `docs/PRD.md`,產出 `docs/ARCHITECTURE.md`,讓 `/linebot-implement` 有足夠資訊直接寫程式。

## 你要做什麼

產出 **`docs/ARCHITECTURE.md`**,包含:

1. **架構圖(文字版)**:LINE Platform → FastAPI `/callback` → Handler 路由 → (Gemini / twstock / SQLite) → reply
2. **模組職責**:webhook entry / 路由分派 / Gemini client / twstock client / DB layer
3. **SQLite schema**:每張表的欄位、PK、用途
4. **環境變數清單**:每個 key 的用途
5. **錯誤處理策略**:哪些錯回友善訊息、哪些直接 raise

## 你不能做什麼

- 不重新定義功能(以 PRD 為準)
- 不寫實作程式碼(留給 `/linebot-implement`)
- 不引入未在 PRD 出現的功能

## 收尾

- 檔名固定:`docs/ARCHITECTURE.md`
- SQLite schema 必須是可以直接貼到 `CREATE TABLE` 的 SQL
- 環境變數清單要與 `.env.example` 對齊
