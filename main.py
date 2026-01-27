import os
import re
import subprocess
import requests
import instaloader
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
CAPTION_TEXT = "<i>скачано с помощью @tiktokbroskibot</i>"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Настройка Instaloader
L = instaloader.Instaloader(user_agent=USER_AGENT)
if os.path.exists(COOKIES_FILE):
    try:
        # Пытаемся загрузить сессию для Instagram фото/каруселей
        L.load_session_from_file("user", filename=COOKIES_FILE)
    except:
        print("Instaloader: Сессия не загружена, работаем в анонимном режиме")

# ================= FLASK (из второго кода) =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/health")
def health():
    return {"status": "healthy"}, 200

def run_flask():
    # Используем порт 3000, как в запросе
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

# ================= UTILS =================
def extract_urls(text: str):
    return re.findall(r'(https?://[^\s]+)', text)

async def get_full_url(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=5)
        return r.url
    except:
        return url

# ================= DOWNLOAD LOGIC =================

async def download_tiktok(update: Update, url: str):
    await update.message.reply_text("⏳ Скачиваю TikTok...")
    try:
        api_url = f"https://www.tikwm.com/api/?url={url}"
        data = requests.get(api_url, timeout=15).json().get('data')
        
        if not data:
            await update.message.reply_text("❌ TikTok контент не найден")
            return

        if 'images' in data and data['images']:
            media = [InputMediaPhoto(img, caption=CAPTION_TEXT if i == 0 else "", parse_mode=ParseMode.HTML) 
                     for i, img in enumerate(data['images'][:10])]
            await update.message.reply_media_group(media)
        else:
            await update.message.reply_video(data['play'], caption=CAPTION_TEXT, parse_mode=ParseMode.HTML)
    except Exception:
        await update.message.reply_text("⚠️ Ошибка при загрузке TikTok")

async def download_instagram(update: Update, url: str):
    await update.message.reply_text("⏳ Скачиваю Instagram...")
    
    # Сначала пробуем Reels через yt-dlp
    output = os.path.join(DOWNLOAD_DIR, "insta_%(id)s.%(ext)s")
    command = [
        "yt-dlp", "--cookies", COOKIES_FILE,
        "--no-check-certificate",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
        "-o", output, url
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, timeout=60)
        files = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith("insta_")]
        if files:
            path = os.path.join(DOWNLOAD_DIR, files[0])
            await update.message.reply_video(video=open(path, "rb"), caption=CAPTION_TEXT, parse_mode=ParseMode.HTML)
            os.remove(path)
            return
    except:
        pass

    # Если не видео или yt-dlp не справился — скачиваем фото/карусели через Instaloader
    try:
        shortcode = re.search(r'/(p|reel|tv)/([^/?#&]+)', url).group(2)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        if post.typename == 'GraphSidecar':
            media = []
            for i, node in enumerate(post.get_sidecar_nodes()):
                if i >= 10: break
                cap = CAPTION_TEXT if i == 0 else ""
                if node.is_video:
                    media.append(InputMediaVideo(node.video_url, caption=cap, parse_mode=ParseMode.HTML))
                else:
                    media.append(InputMediaPhoto(node.display_url, caption=cap, parse_mode=ParseMode.HTML))
            await update.message.reply_media_group(media)
        elif post.is_video:
            await update.message.reply_video(post.video_url, caption=CAPTION_TEXT, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_photo(post.url, caption=CAPTION_TEXT, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось скачать Instagram: {e}")

async def download_pinterest(update: Update, url: str):
    await update.message.reply_text("⏳ Скачиваю Pinterest...")
    
    # Пытаемся скачать как видео через yt-dlp
    output = os.path.join(DOWNLOAD_DIR, "pin_%(id)s.%(ext)s")
    try:
        subprocess.run(["yt-dlp", "-o", output, url], check=True, timeout=30)
        files = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith("pin_")]
        if files:
            path = os.path.join(DOWNLOAD_DIR, files[0])
            if path.endswith(".mp4"):
                await update.message.reply_video(open(path, "rb"), caption=CAPTION_TEXT, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_photo(open(path, "rb"), caption=CAPTION_TEXT, parse_mode=ParseMode.HTML)
            os.remove(path)
            return
    except:
        pass

    # Если yt-dlp не взял, пробуем как прямое фото
    try:
        res = requests.get(url, headers={'User-Agent': USER_AGENT})
        soup = BeautifulSoup(res.content, 'html.parser')
        img = soup.find('meta', property='og:image')
        if img:
            await update.message.reply_photo(img['content'], caption=CAPTION_TEXT, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Контент Pinterest не найден")
    except Exception:
        await update.message.reply_text("❌ Ошибка Pinterest")

# ================= HANDLERS =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = extract_urls(update.message.text)
    if not urls:
        return

    url = await get_full_url(urls[0])

    if "tiktok.com" in url:
        await download_tiktok(update, url)
    elif "instagram.com" in url:
        await download_instagram(update, url)
    elif "pinterest.com" in url or "pin.it" in url:
        await download_pinterest(update, url)
    else:
        await update.message.reply_text("❌ Ссылка не поддерживается")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>🤖 Multi Downloader Bot</b>\n\nПришли ссылку на TikTok, Pinterest или Instagram!",
        parse_mode=ParseMode.HTML
    )

# ================= MAIN =================

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан")
        return

    # Запуск Flask в отдельном потоке
    Thread(target=run_flask, daemon=True).start()

    # Запуск бота
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start_command))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app_bot.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
