import logging
import os
import sqlite3
from datetime import datetime, timezone

import google.generativeai as genai
import twstock
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("linebot")

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = os.getenv("DB_PATH", "users.db")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET or not GEMINI_API_KEY:
    raise RuntimeError(
        "缺少必要環境變數,請檢查 .env 是否設定 "
        "LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET / GEMINI_API_KEY"
    )

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
gemini_model = genai.GenerativeModel(GEMINI_MODEL)

app = FastAPI(title="Stock LINE Bot")


def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as conn:
        conn.executescript(
            """
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
            """
        )


init_db()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_user(user_id: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id, joined_at) VALUES (?, ?)",
            (user_id, now_iso()),
        )


def log_interaction(user_id: str, message: str, reply: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO interactions(user_id, message, reply, ts) VALUES (?, ?, ?, ?)",
            (user_id, message, reply, now_iso()),
        )


def add_watchlist(user_id: str, stock_id: str) -> str:
    with db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO watchlist(user_id, stock_id, added_at) VALUES (?, ?, ?)",
            (user_id, stock_id, now_iso()),
        )
    if cur.rowcount == 0:
        return f"{stock_id} 已在你的清單裡了"
    return f"已加入追蹤:{stock_id}"


def list_watchlist(user_id: str) -> str:
    with db() as conn:
        rows = conn.execute(
            "SELECT stock_id, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        ).fetchall()
    if not rows:
        return "你的追蹤清單是空的,試試傳「追蹤 2330」"
    lines = ["你的追蹤清單:"]
    for stock_id, _ in rows:
        lines.append(f"  • {stock_id}")
    return "\n".join(lines)


def remove_watchlist(user_id: str, stock_id: str) -> str:
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND stock_id = ?",
            (user_id, stock_id),
        )
    if cur.rowcount == 0:
        return f"{stock_id} 不在你的清單裡"
    return f"已移除:{stock_id}"


def quote_stock(stock_id: str) -> str:
    try:
        result = twstock.realtime.get(stock_id)
    except Exception as e:
        log.exception("twstock 失敗")
        return f"查詢失敗:{e}"
    if not result or not result.get("success"):
        return f"查無此股號:{stock_id}(請確認是台股代號,例如 2330)"
    info = result.get("info", {})
    realtime = result.get("realtime", {})
    name = info.get("name", "?")
    code = info.get("code", stock_id)
    open_price = realtime.get("open", "-")
    high = realtime.get("high", "-")
    low = realtime.get("low", "-")
    latest_trade_price = realtime.get("latest_trade_price", "-")
    trade_volume = realtime.get("accumulate_trade_volume", "-")
    return (
        f"📊 {name} ({code})\n"
        f"成交:{latest_trade_price}\n"
        f"開盤:{open_price}\n"
        f"最高:{high}\n"
        f"最低:{low}\n"
        f"累積成交量:{trade_volume}"
    )


def analyze_stock(query: str) -> str:
    prompt = (
        f"你是一位台股分析師,請針對「{query}」這檔股票或公司,"
        "用中文寫一份 200 字內的簡短分析,涵蓋:\n"
        "1. 公司主要業務或產業地位\n"
        "2. 近期題材或催化劑\n"
        "3. 主要風險\n"
        "用條列式,不要免責聲明,不要重複問題本身。"
    )
    try:
        resp = gemini_model.generate_content(prompt)
        text = (resp.text or "").strip()
    except Exception as e:
        log.exception("Gemini 失敗")
        return f"分析失敗(可能 API 額度用盡):{e}"
    if not text:
        return "Gemini 沒有回傳內容,請換個股票試試"
    return text


MENU = (
    "📈 股票 LINE Bot 指令\n"
    "─────────────\n"
    "查詢 2330       → 即時報價\n"
    "分析 台積電     → AI 分析\n"
    "追蹤 2330       → 加入清單\n"
    "清單            → 看清單\n"
    "刪除 2330       → 移除\n"
    "選單            → 顯示此說明"
)


COMMANDS = ("查詢", "分析", "追蹤", "刪除", "清單", "選單", "幫助")


def split_command(text: str) -> tuple[str, str]:
    head, _, rest = text.partition(" ")
    if rest or head in COMMANDS:
        return head.strip(), rest.strip()
    for cmd in COMMANDS:
        if text.startswith(cmd):
            return cmd, text[len(cmd):].strip()
    return text.strip(), ""


def route(user_id: str, text: str) -> str:
    text = text.strip()
    if not text:
        return MENU
    head, rest = split_command(text)

    if head in ("選單", "menu", "help", "幫助"):
        return MENU
    if head == "清單":
        return list_watchlist(user_id)
    if head == "查詢":
        if not rest:
            return "用法:查詢 2330"
        return quote_stock(rest)
    if head == "分析":
        if not rest:
            return "用法:分析 台積電"
        return analyze_stock(rest)
    if head == "追蹤":
        if not rest:
            return "用法:追蹤 2330"
        return add_watchlist(user_id, rest)
    if head == "刪除":
        if not rest:
            return "用法:刪除 2330"
        return remove_watchlist(user_id, rest)
    return MENU


@app.get("/")
def root():
    return {"status": "ok", "service": "stock-line-bot"}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        log.exception("webhook 例外,但仍回 200 避免 LINE 重試")
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    user_id = event.source.user_id if event.source and event.source.user_id else "unknown"
    text = event.message.text or ""

    ensure_user(user_id)
    try:
        reply = route(user_id, text)
    except Exception as e:
        log.exception("route 例外")
        reply = f"系統錯誤,請稍後再試:{e}"

    reply = reply[:4900]
    log_interaction(user_id, text, reply)

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)],
            )
        )
