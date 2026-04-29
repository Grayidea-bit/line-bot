---
name: commit
description: 看 git diff 與 git status,產出符合 Conventional Commits 的提交訊息並執行 commit。
---

# /commit

幫使用者把目前的變更寫成 conventional commit。

## 你要做什麼

1. 跑 `git status`、`git diff --staged`、`git diff`(未 staged 的)
2. 判斷變更性質:
   - 新增功能 → `feat`
   - 修 bug → `fix`
   - 重構 → `refactor`
   - 文件 → `docs`
   - 設定 / 工具 → `chore`
   - 測試 → `test`
3. 產出格式:`<type>(<scope>): <subject>`,subject 用中文或英文皆可,**祈使句、不超過 60 字**
4. 若變更跨多個邏輯模組,建議分多個 commit
5. 執行 `git add` + `git commit -m "..."`

## 你不能做什麼

- **不能** `git add -A` 或 `git add .`(可能 commit 到 `.env` 或 `users.db`)
- **不能** `--no-verify`、`--no-gpg-sign`
- **不能** push 除非使用者明確說
- 看到 `.env`、`users.db`、token 字串出現在 diff 就**停下來警告使用者**

## 收尾

- 訊息只給一行 subject + 空行 + 1-3 行 body(若需要)
- 不加 emoji 除非使用者已有此習慣
- commit 完後跑 `git status` 驗證
