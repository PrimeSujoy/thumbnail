import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

# ========= CONFIG =========
BOT_TOKEN = "8419073003:AAFG1YujfPnjlZ29KjDw1CqCte7p_f0WLTQ"
DB_PATH = "thumbs.db"
# ==========================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


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
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    await msg.answer(
        "🎬 Instant Thumbnail Bot\n\n"
        "📸 Send PHOTO → thumbnail saved\n"
        "🎥 Send VIDEO → I resend with your thumbnail cover\n\n"
        "/thumb - view thumbnail\n"
        "/clear - remove thumbnail"
    )


@dp.message(Command("thumb"))
async def thumb_cmd(msg: Message):
    thumb = await get_thumb(msg.from_user.id)
    if not thumb:
        return await msg.answer("❌ No thumbnail set. Send a photo first.")
    await msg.answer_photo(thumb, caption="🖼 Your current thumbnail")


@dp.message(Command("clear"))
async def clear_cmd(msg: Message):
    ok = await clear_thumb(msg.from_user.id)
    await msg.answer("🗑 Thumbnail removed" if ok else "❌ No thumbnail to remove")


# ---------- Auto set thumb from photo ----------
@dp.message(F.photo)
async def photo_handler(msg: Message):
    file_id = msg.photo[-1].file_id
    await set_thumb(msg.from_user.id, file_id)
    await msg.answer("✅ Thumbnail saved! Now send a video.")


# ---------- Apply thumb to video using send_cached_media ----------
@dp.message(F.video)
async def video_handler(msg: Message):
    thumb = await get_thumb(msg.from_user.id)
    if not thumb:
        return await msg.answer("⚠️ No thumbnail set. Send a photo first.")

    caption = msg.caption
    caption_entities = msg.caption_entities

    try:
        # send_cached_media should work with video file_id too (Telegram cached file)
        await bot.send_cached_media(
            chat_id=msg.chat.id,
            file_id=msg.video.file_id,
            caption=caption,
            caption_entities=caption_entities,
            cover=thumb,
        )
    except Exception as e:
        # fallback: still preserve caption formatting
        await msg.answer(f"⚠️ send_cached_media failed ({type(e).__name__}). Falling back to send_video…")
        try:
            await bot.send_video(
                chat_id=msg.chat.id,
                video=msg.video.file_id,
                caption=caption,
                caption_entities=caption_entities,
                cover=thumb,
            )
        except Exception:
            await bot.send_video(
                chat_id=msg.chat.id,
                video=msg.video.file_id,
                caption=caption,
                caption_entities=caption_entities,
            )


# ---------- Run ----------
async def main():
    await init_db()
    print("✅ Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
