import asyncio
import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 Привет! Отправь ссылку на Instagram Reel, и я его скачаю."
    )


@dp.message()
async def download_reel(message: types.Message):
    url = message.text.strip()

    if "instagram.com" not in url:
        await message.answer("❌ Это не ссылка на Instagram Reel")
        return

    await message.answer("⏳ Скачиваю видео...")

    output_path = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "-f", "b[ext=mp4]",  # лучший mp4 формат
        "-o", output_path,
        url
    ]

    try:
        subprocess.run(command, check=True)

        # отправляем последний скачанный файл
        files = sorted(
            os.listdir(DOWNLOAD_DIR),
            key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)),
            reverse=True
        )

        video_path = os.path.join(DOWNLOAD_DIR, files[0])

        await message.answer_video(
            video=types.FSInputFile(video_path),
            caption="✅ Готово!"
        )

        os.remove(video_path)

    except Exception as e:
        await message.answer(f"❌ Не удалось скачать Reel. Ошибка: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
