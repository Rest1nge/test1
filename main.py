import os
import re
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import subprocess
import instaloader

BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/health")
def health():
    return {"status": "healthy"}, 200

def extract_urls(text: str):
    return re.findall(r"(https?://[^\s]+)", text)

def clean_downloads():
    for f in os.listdir(DOWNLOAD_DIR):
        os.remove(os.path.join(DOWNLOAD_DIR, f))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Отправь ссылку — я скачаю фото или видео.\nПоддержка:\n"
        "• TikTok\n• Instagram\n• Pinterest\n• YouTube Shorts"
    )

# ===========================
# Download functions
# ===========================

async def download_tiktok(url):
    # yt-dlp
    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    cmd = ["yt-dlp", "-f", "bv*+ba/best", "--merge-output-format", "mp4", "-o", output, url]
    subprocess.run(cmd, check=False)
    return sorted(os.listdir(DOWNLOAD_DIR), key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)))

async def download_youtube(url):
    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    cmd = ["yt-dlp", "-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4", "-o", output, url]
    subprocess.run(cmd, check=False)
    return sorted(os.listdir(DOWNLOAD_DIR), key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)))

async def download_instagram_post(url):
    clean_downloads()
    L = instaloader.Instaloader(download_videos=True, download_comments=False, save_metadata=False, dirname_pattern=DOWNLOAD_DIR)
    try:
        shortcode = url.rstrip("/").split("/")[-1]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=DOWNLOAD_DIR)
    except Exception as e:
        print("Instagram error:", e)
    return sorted(os.listdir(DOWNLOAD_DIR), key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)))

async def download_pinterest(url):
    clean_downloads()
    # Pinterest image only: get direct image URL
    try:
        r = requests.get(url, timeout=10).text
        img_urls = re.findall(r'"images":\{"orig":\{"url":"(https:[^"]+)"\}', r)
        for i, img_url in enumerate(img_urls):
            ext = img_url.split(".")[-1].split("?")[0]
            path = os.path.join(DOWNLOAD_DIR, f"pin_{i}.{ext}")
            with open(path, "wb") as f:
                f.write(requests.get(img_url).content)
    except:
        pass
    return sorted(os.listdir(DOWNLOAD_DIR), key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)))

# ===========================
# Main handler
# ===========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = extract_urls(update.message.text)
    if not urls:
        await update.message.reply_text("❌ Ссылки не найдено")
        return

    url = urls[0]
    clean_downloads()
    files = []

    if "tiktok.com" in url:
        files = await download_tiktok(url)
    elif "youtube.com" in url or "youtu.be" in url:
        files = await download_youtube(url)
    elif "instagram.com/p/" in url:
        files = await download_instagram_post(url)
    elif "pinterest.com" in url:
        files = await download_pinterest(url)
    else:
        await update.message.reply_text("❌ Платформа не поддерживается")
        return

    if not files:
        await update.message.reply_text("❌ Контент не найден")
        return

    for f in files:
        path = os.path.join(DOWNLOAD_DIR, f)
        ext = f.lower()
        if ext.endswith((".mp4", ".webm", ".mov")):
            await update.message.reply_video(open(path, "rb"), caption="скачано с помощью @instbotsavebot")
        elif ext.endswith((".jpg", ".jpeg", ".png")):
            await update.message.reply_photo(open(path, "rb"))
        else:
            await update.message.reply_document(open(path, "rb"))
        os.remove(path)

# ===========================
# Start bot
# ===========================

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан")
        return

    Thread(target=run_flask, daemon=True).start()
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start_command))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
