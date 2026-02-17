import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command

# ================= CONFIG =================
BOT_TOKEN = "8419073003:AAFG1YujfPnjlZ29KjDw1CqCte7p_f0WLTQ"
DB_PATH = "thumbs.db"

# ==========================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ================= DATABASE =================
async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_thumbs (
                user_id INTEGER PRIMARY KEY,
                file_id TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        await db.commit()


async def set_thumb(user_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_thumbs(user_id, file_id, updated_at)
            VALUES (?, ?, strftime('%s','now'))
            ON CONFLICT(user_id)
            DO UPDATE SET
                file_id=excluded.file_id,
                updated_at=excluded.updated_at
            """,
            (user_id, file_id),
        )
        await db.commit()


async def get_thumb(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT file_id FROM user_thumbs WHERE user_id=?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def clear_thumb(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM user_thumbs WHERE user_id=?",
            (user_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


# ================= COMMANDS =================
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    await msg.answer(
        "🎬 Instant Thumbnail Bot\n\n"
        "Send a PHOTO → auto set thumbnail\n"
        "Send a VIDEO → thumbnail applied instantly\n\n"
        "/thumb → view thumbnail\n"
        "/clear → remove thumbnail"
    )


@dp.message(Command("thumb"))
async def thumb_cmd(msg: Message):
    thumb = await get_thumb(msg.from_user.id)

    if not thumb:
        await msg.answer("❌ No thumbnail set.\nSend a photo first.")
        return

    await msg.answer_photo(
        thumb,
        caption="🖼 Your current thumbnail"
    )


@dp.message(Command("clear"))
async def clear_cmd(msg: Message):
    removed = await clear_thumb(msg.from_user.id)

    if removed:
        await msg.answer("🗑 Thumbnail removed")
    else:
        await msg.answer("❌ No thumbnail found")


# ================= PHOTO HANDLER =================
@dp.message(F.photo)
async def photo_handler(msg: Message):
    file_id = msg.photo[-1].file_id

    await set_thumb(msg.from_user.id, file_id)

    await msg.answer(
        "✅ Thumbnail saved successfully!\n"
        "Now send a video."
    )


# ================= VIDEO HANDLER =================
@dp.message(F.video)
async def video_handler(msg: Message):
    thumb = await get_thumb(msg.from_user.id)

    if not thumb:
        await msg.answer(
            "⚠ No thumbnail set.\n"
            "Send a photo first."
        )
        return

    caption = msg.caption or ""

    try:
        await bot.send_video(
            chat_id=msg.chat.id,
            video=msg.video.file_id,
            caption=caption,
            cover=thumb,
        )
    except Exception:
        await bot.send_video(
            chat_id=msg.chat.id,
            video=msg.video.file_id,
            caption=caption,
        )


# ================= RUN =================
async def main():
    await db_init()
    print("Bot started successfully!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
