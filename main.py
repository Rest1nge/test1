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
        "👋 Привет! Отправь ссылку на Instagram Reel, и я его скачаю.\n"
        "⚠️ Работает только с публичными Reels."
    )


@dp.message()
async def download_reel(message: types.Message):
    url = message.text.strip()

    # убираем параметры после ?
    if '?' in url:
        url = url.split('?')[0]

    if "instagram.com" not in url or "/reel/" not in url:
        await message.answer("❌ Это не ссылка на Instagram Reel")
        return

    await message.answer("⏳ Скачиваю видео...")

    output_path = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "--no-check-certificate",  # помогает при проблемах с SSL
        "-f", "b[ext=mp4]",        # лучший mp4
        "-o", output_path,
        url
    ]

    try:
        subprocess.run(command, check=True)

        # получаем последний скачанный файл
        files = sorted(
            os.listdir(DOWNLOAD_DIR),
            key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)),
            reverse=True
        )

        if not files:
            await message.answer("❌ Не удалось скачать видео. Возможно, Reel приватный или удалён.")
            return

        video_path = os.path.join(DOWNLOAD_DIR, files[0])

        await message.answer_video(
            video=types.FSInputFile(video_path),
            caption="✅ Готово! Видео успешно скачано."
        )

        os.remove(video_path)

    except subprocess.CalledProcessError:
        await message.answer("❌ Не удалось скачать видео. Возможно, Reel приватный или ссылка неверная.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
