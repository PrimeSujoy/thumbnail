import asyncio
import aiosqlite
import aiohttp

from pyrogram import Client, filters, idle
from pyrogram.types import Message

# ================== CONFIG ==================
API_ID = "22182189"
API_HASH = "8419073003:AAFG1YujfPnjlZ29KjDw1CqCte7p_f0WLTQ"
BOT_TOKEN = "8419073003:AAFG1YujfPnjlZ29KjDw1CqCte7p_f0WLTQ"

DB_PATH = "thumbs.db"

# Your FastAPI/Aiogram service (running on same VPS)
API_URL = "http://127.0.0.1:8008/send_cover_video"
# ===========================================

app = Client(
    "thumb_pyro_api_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------- DB ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS thumbs (
                user_id INTEGER PRIMARY KEY,
                file_id TEXT NOT NULL
            )
        """)
        await db.commit()

async def set_thumb(user_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO thumbs(user_id, file_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET file_id=excluded.file_id
        """, (user_id, file_id))
        await db.commit()

async def get_thumb(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT file_id FROM thumbs WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def clear_thumb(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM thumbs WHERE user_id=?", (user_id,))
        await db.commit()
        return cur.rowcount > 0


# ---------- API Caller ----------
async def send_cover_via_api(chat_id: int, video_file_id: str, thumb_file_id: str,
                             caption: str | None, caption_entities):
    # caption_entities from pyrogram are objects -> convert to dict
    entities_payload = None
    if caption_entities:
        entities_payload = [e.to_dict() for e in caption_entities]

    payload = {
        "chat_id": chat_id,
        "video_file_id": video_file_id,
        "thumb_file_id": thumb_file_id,
        "caption": caption,
        "caption_entities": entities_payload,
        "protect_content": False,
    }

    async with aiohttp.ClientSession() as s:
        async with s.post(API_URL, json=payload, timeout=90) as r:
            text = await r.text()
            if r.status != 200:
                raise RuntimeError(f"API {r.status}: {text}")
            return text


# ---------- Commands ----------
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(_, msg: Message):
    await msg.reply_text(
        "🎬 *Instant Thumbnail Bot (Pyrogram → API)*\n\n"
        "📸 Send PHOTO → thumbnail saved\n"
        "🎥 Send VIDEO → I resend with your cover via API\n\n"
        "/thumb - view thumbnail\n"
        "/clear - remove thumbnail",
        quote=True
    )

@app.on_message(filters.private & filters.command("thumb"))
async def thumb_cmd(_, msg: Message):
    thumb = await get_thumb(msg.from_user.id)
    if not thumb:
        return await msg.reply_text("❌ No thumbnail set. Send a photo first.")
    try:
        await msg.reply_photo(thumb, caption="🖼 Your current thumbnail.")
    except Exception:
        # If thumb is invalid, clear and ask to re-send
        await clear_thumb(msg.from_user.id)
        await msg.reply_text("⚠️ Your stored thumbnail was invalid. Please send a new photo.")

@app.on_message(filters.private & filters.command("clear"))
async def clear_cmd(_, msg: Message):
    ok = await clear_thumb(msg.from_user.id)
    await msg.reply_text("🗑 Thumbnail removed." if ok else "❌ No thumbnail to remove.")


# ---------- Save thumb ----------
@app.on_message(filters.private & filters.photo)
async def photo_handler(_, msg: Message):
    # highest quality photo is last in list (in pyrogram msg.photo is Photo object)
    file_id = msg.photo.file_id
    await set_thumb(msg.from_user.id, file_id)
    await msg.reply_text("✅ Thumbnail saved! Now send a video.")


# ---------- Handle video ----------
@app.on_message(filters.private & filters.video)
async def video_handler(_, msg: Message):
    thumb = await get_thumb(msg.from_user.id)
    if not thumb:
        return await msg.reply_text("⚠️ No thumbnail set. Send a photo first.")

    caption = msg.caption
    caption_entities = msg.caption_entities

    try:
        await send_cover_via_api(
            chat_id=msg.chat.id,
            video_file_id=msg.video.file_id,
            thumb_file_id=thumb,
            caption=caption,
            caption_entities=caption_entities
        )
    except Exception as e:
        # fallback: send normal video without cover but keep formatting
        await msg.reply_text(f"⚠️
