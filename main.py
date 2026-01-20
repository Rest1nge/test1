import os
import subprocess
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================== FLASK ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running", 200

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

# ================== TELEGRAM ==================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🤖 *Multi Downloader Bot*

Я умею скачивать:
• *TikTok* — без водяного знака
• *Pinterest* — фото и видео
• *Instagram Reels* — стабильно (cookies)

📌 Просто отправь ссылку
    """
    await update.message.reply_text(text, parse_mode="Markdown")

# -------- TikTok --------
async def download_tiktok(update, url):
    api_url = f"https://www.tikwm.com/api/?url={url}"
    try:
        data = requests.get(api_url, timeout=15).json()
        if data.get("code") == 0:
            await update.message.reply_video(data["data"]["play"])
        else:
            await update.message.reply_text("⚠️ TikTok видео не найдено")
    except:
        await update.message.reply_text("⚠️ Ошибка при загрузке TikTok")

# -------- Pinterest --------
async def download_pinterest(update, url):
    await update.message.reply_text("⏳ Скачиваю Pinterest...")

    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "-f", "bv*+ba/b",
        "-o", output,
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
            await update.message.reply_text("❌ Контент не найден")
            return

        path = os.path.join(DOWNLOAD_DIR, files[0])

        if path.endswith(".mp4"):
            await update.message.reply_video(video=open(path, "rb"))
        else:
            await update.message.reply_photo(photo=open(path, "rb"))

        os.remove(path)

    except subprocess.CalledProcessError:
        await update.message.reply_text("❌ Не удалось скачать Pinterest контент")
pdate.message.reply_text("⚠️ Ошибка Pinterest")

# -------- Instagram Reels (yt-dlp + cookies) --------
async def download_instagram(update, url):
    if not os.path.exists(COOKIES_FILE):
        await update.message.reply_text("❌ cookies.txt не найден")
        return

    await update.message.reply_text("⏳ Скачиваю Instagram Reel...")

    if "?" in url:
        url = url.split("?")[0]

    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "--no-check-certificate",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
        "-o", output,
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
            await update.message.reply_text("❌ Видео не найдено")
            return

        video_path = os.path.join(DOWNLOAD_DIR, files[0])
        await update.message.reply_video(video=open(video_path, "rb"))
        os.remove(video_path)

    except subprocess.CalledProcessError:
        await update.message.reply_text(
            "❌ Не удалось скачать Reel\n"
            "• Видео удалено\n"
            "• Приватный доступ\n"
            "• Cookies устарели"
        )

# -------- URL Resolver --------
async def get_full_url(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=5)
        return r.url
    except:
        return url

# -------- MAIN HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_url = update.message.text.strip()
    await update.message.reply_chat_action("typing")

    url = await get_full_url(raw_url)

    if "tiktok.com" in url:
        await download_tiktok(update, url)
    elif "pinterest.com" in url or "pin.it" in url:
        await download_pinterest(update, url)
    elif "instagram.com/reel/" in url:
        await download_instagram(update, url)
    else:
        await update.message.reply_text("❌ Ссылка не поддерживается")

# ================== START ==================
def run_flask():
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан")
        return

    Thread(target=run_flask, daemon=True).start()

    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start_command))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    bot.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
