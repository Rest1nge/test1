import asyncio
import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 Отправь ссылку на Instagram Reel.\n"
        "✅ Работает стабильно (cookies включены)."
    )


@dp.message()
async def download_reel(message: types.Message):
    url = message.text.strip()

    # очистка ссылки
    if "?" in url:
        url = url.split("?")[0]

    if "instagram.com/reel/" not in url:
        await message.answer("❌ Это не ссылка на Instagram Reel")
        return

    if not os.path.exists(COOKIES_FILE):
        await message.answer("❌ Файл cookies.txt не найден")
        return

    await message.answer("⏳ Скачиваю видео...")

    output_path = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "--no-check-certificate",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
        "-o", output_path,
        url
    ]

    try:
        subprocess.run(command, check=True)

        files = sorted(
            os.listdir(DOWNLOAD_DIR),
            key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)),
            reverse=True
        )

        if not files:
            await message.answer("❌ Видео не найдено")
            return

        video_path = os.path.join(DOWNLOAD_DIR, files[0])

        await message.answer_video(
            video=types.FSInputFile(video_path),
            caption="✅ Готово"
        )

        os.remove(video_path)

    except subprocess.CalledProcessError:
        await message.answer(
            "❌ Не удалось скачать Reel.\n"
            "Причины:\n"
            "• Видео удалено\n"
            "• Аккаунт ограничен\n"
            "• Cookies устарели"
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
