import asyncio
import aiosqlite
from pyrogram import Client, filters
from pyrogram.types import Message

# ========= CONFIG =========
API_ID = "22182189"
API_HASH = "5e7c4088f8e23d0ab61e29ae11960bf5"
BOT_TOKEN = "8419073003:AAFG1YujfPnjlZ29KjDw1CqCte7p_f0WLTQ"
DB_PATH = "thumbs.db"
# ==========================

app = Client(
    "thumb_test_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
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


# ---------- Commands ----------
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(_, msg: Message):
    await msg.reply_text(
        "🎬 Thumbnail Cover Test (pyrofork)\n\n"
        "📸 Send PHOTO → thumbnail saved\n"
        "🎥 Send VIDEO → resend with cover using send_cached_media\n\n"
        "/thumb - view thumbnail\n"
        "/clear - remove thumbnail"
    )

@app.on_message(filters.private & filters.command("thumb"))
async def thumb_cmd(_, msg: Message):
    thumb = await get_thumb(msg.from_user.id)
    if not thumb:
        return await msg.reply_text("❌ No thumbnail set. Send a photo first.")
    await msg.reply_photo(thumb, caption="🖼 Your current thumbnail")

@app.on_message(filters.private & filters.command("clear"))
async def clear_cmd(_, msg: Message):
    ok = await clear_thumb(msg.from_user.id)
    await msg.reply_text("🗑 Thumbnail removed" if ok else "❌ No thumbnail to remove")


# ---------- Save thumb ----------
@app.on_message(filters.private & filters.photo)
async def photo_handler(_, msg: Message):
    # highest quality photo is usually last
    file_id = msg.photo.file_id if hasattr(msg.photo, "file_id") else msg.photo[-1].file_id
    await set_thumb(msg.from_user.id, file_id)
    await msg.reply_text("✅ Thumbnail saved! Now send a video.")


# ---------- Apply cover to video ----------
@app.on_message(filters.private & filters.video)
async def video_handler(client: Client, msg: Message):
    thumb = await get_thumb(msg.from_user.id)
    if not thumb:
        return await msg.reply_text("⚠️ No thumbnail set. Send a photo first.")

    caption = msg.caption
    caption_entities = msg.caption_entities

    # 1) Try the exact concept: send_cached_media + cover
    try:
        await client.send_cached_media(
            chat_id=msg.chat.id,
            file_id=msg.video.file_id,
            caption=caption,
            caption_entities=caption_entities,
            cover=thumb,
        )
        return
    except Exception as e1:
        await msg.reply_text(f"⚠️ send_cached_media cover failed ({type(e1).__name__}). Trying send_video...")

    # 2) Fallback: send_video + cover
    try:
        await client.send_video(
            chat_id=msg.chat.id,
            video=msg.video.file_id,
            caption=caption,
            caption_entities=caption_entities,
            cover=thumb,
        )
        return
    except Exception as e2:
        await msg.reply_text(f"⚠️ send_video cover failed ({type(e2).__name__}). Sending without cover...")

    # 3) Final fallback: without cover
    await client.send_video(
        chat_id=msg.chat.id,
        video=msg.video.file_id,
        caption=caption,
        caption_entities=caption_entities,
    )


if __name__ == "__main__":
    asyncio.run(init_db())
    print("✅ Bot started (pyrofork test)!")
    app.run()
