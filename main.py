import telebot
import os
import requests
from bs4 import BeautifulSoup
import instaloader
import re
import shutil
import http.cookiejar
from flask import Flask
from threading import Thread
from telebot import types

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
COOKIE_FILE = 'cookies.txt'
DOWNLOAD_FOLDER = "downloads"

bot = telebot.TeleBot(BOT_TOKEN)
L = instaloader.Instaloader(user_agent=USER_AGENT)

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- FLASK СЕРВЕР ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running via Cookies with TikTok support!", 200

@app.route("/health")
def health():
    return {"status": "healthy"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- НАСТРОЙКА INSTAGRAM ---
def setup_instagram():
    if os.path.exists(COOKIE_FILE):
        try:
            print("Настраиваем сессию Instagram...")
            cj = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
            cj.load(ignore_discard=True, ignore_expires=True)
            L.context._session.cookies.update(cj)
            L.context._session.headers.update({'User-Agent': USER_AGENT})
            username = L.test_login()
            if username:
                print(f"Успешно авторизованы в Insta как: {username}")
        except Exception as e:
            print(f"Ошибка Instagram-авторизации: {e}")
    else:
        print("ВНИМАНИЕ: Файл cookies.txt не найден!")

setup_instagram()

# --- ЛОГИКА ЗАГРУЗКИ ---

def get_tiktok_content(url):
    try:
        # Используем сторонний API для получения прямых ссылок TikTok
        api_url = f"https://www.tikwm.com/api/?url={url}"
        response = requests.get(api_url).json()
        data = response.get('data')
        
        if not data:
            return None
        
        # Если это слайд-шоу (фотографии)
        if 'images' in data and data['images']:
            return [{'url': img, 'is_video': False} for img in data['images']]
        
        # Если это видео
        if 'play' in data:
            return [{'url': data['play'], 'is_video': True}]
            
        return None
    except Exception as e:
        print(f"TikTok Error: {e}")
        return None

def get_insta_content(url):
    try:
        shortcode_match = re.search(r'/(p|reel|tv)/([^/?#&]+)', url)
        if not shortcode_match: return None
        shortcode = shortcode_match.group(2)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        if post.typename == 'GraphSidecar':
            media_urls = []
            for node in post.get_sidecar_nodes():
                media_urls.append({
                    'url': node.video_url if node.is_video else node.display_url, 
                    'is_video': node.is_video
                })
            return media_urls
        return [{'url': post.video_url if post.is_video else post.url, 'is_video': post.is_video}]
    except Exception as e:
        print(f"Instagram Error: {e}")
        return None

def download_pinterest(url, chat_id):
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.content, 'html.parser')
        image_tag = soup.find('meta', property='og:image')
        if image_tag:
            img_data = requests.get(image_tag['content']).content
            filename = f"{DOWNLOAD_FOLDER}/pin_{chat_id}.jpg"
            with open(filename, 'wb') as handler: handler.write(img_data)
            return filename
        return None
    except Exception as e:
        print(f"Pinterest Error: {e}")
        return None

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
@bot.message_handler(content_types=['text'])
def handle_message(message):
    url = message.text
    chat_id = message.chat.id
    
    if "pinterest.com" in url or "pin.it" in url:
        bot.send_message(chat_id, "Pinterest: качаю...")
        path = download_pinterest(url, chat_id)
        if path:
            with open(path, 'rb') as f: bot.send_photo(chat_id, f)
            os.remove(path)
        else:
            bot.send_message(chat_id, "Ошибка Pinterest.")

    elif "instagram.com" in url:
        bot.send_message(chat_id, "Instagram: извлекаю контент...")
        results = get_insta_content(url)
        process_media_results(chat_id, results)

    elif "tiktok.com" in url:
        bot.send_message(chat_id, "TikTok: извлекаю контент...")
        results = get_tiktok_content(url)
        process_media_results(chat_id, results)

    else:
        bot.send_message(chat_id, "Жду ссылку на Instagram, Pinterest или TikTok...")

def process_media_results(chat_id, results):
    if not results:
        bot.send_message(chat_id, "Не удалось скачать контент. Проверьте ссылку или настройки.")
        return

    try:
        if len(results) == 1:
            item = results[0]
            if item['is_video']:
                bot.send_video(chat_id, item['url'])
            else:
                bot.send_photo(chat_id, item['url'])
        else:
            media_group = []
            for i, entry in enumerate(results):
                if i >= 10: break # Лимит Telegram на альбомы
                if entry['is_video']:
                    media_group.append(types.InputMediaVideo(entry['url']))
                else:
                    media_group.append(types.InputMediaPhoto(entry['url']))
            bot.send_media_group(chat_id, media_group)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при отправке: {e}")

# --- ЗАПУСК ---
if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    print("Бот запущен...")
    bot.infinity_polling()
