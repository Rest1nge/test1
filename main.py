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
# Убедитесь, что переменная BOT_TOKEN установлена в окружении вашего хостинга
BOT_TOKEN = os.environ.get('BOT_TOKEN')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
COOKIE_FILE = 'cookies.txt'
DOWNLOAD_FOLDER = "downloads"

bot = telebot.TeleBot(BOT_TOKEN)
L = instaloader.Instaloader(user_agent=USER_AGENT)

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- FLASK СЕРВЕР ДЛЯ ПОДДЕРЖКИ ЖИЗНЕДЕЯТЕЛЬНОСТИ ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active with Cookie-based auth and Multi-photo support!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- АВТОРИЗАЦИЯ В INSTAGRAM ---
def setup_instagram():
    if os.path.exists(COOKIE_FILE):
        try:
            print(f"Загрузка куки из {COOKIE_FILE}...")
            cj = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
            cj.load(ignore_discard=True, ignore_expires=True)
            L.context._session.cookies.update(cj)
            L.context._session.headers.update({'User-Agent': USER_AGENT})
            
            username = L.test_login()
            if username:
                print(f"Успешный вход под аккаунтом: {username}")
            else:
                print("Не удалось подтвердить вход. Проверьте актуальность cookies.txt.")
        except Exception as e:
            print(f"Критическая ошибка при загрузке куки: {e}")
    else:
        print("Файл cookies.txt не найден. Работа в анонимном режиме ограничена.")

setup_instagram()

# --- ЛОГИКА ОБРАБОТКИ INSTAGRAM ---
def get_insta_content(url):
    try:
        # Поиск шорткода (p, reel или tv)
        match = re.search(r'/(p|reel|tv)/([^/?#&]+)', url)
        if not match:
            return None
        
        shortcode = match.group(2)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Если это карусель (несколько фото/видео)
        if post.typename == 'GraphSidecar':
            media_urls = []
            for node in post.get_sidecar_nodes():
                # Добавляем URL (видео или фото)
                media_urls.append({'url': node.video_url if node.is_video else node.display_url, 'is_video': node.is_video})
            return media_urls
        
        # Если одиночный пост или Reels
        return [{'url': post.video_url if post.is_video else post.url, 'is_video': post.is_video}]
    
    except Exception as e:
        print(f"Instaloader error: {e}")
        return None

# --- ЛОГИКА ОБРАБОТКИ PINTEREST ---
def get_pinterest_image(url, chat_id):
    try:
        headers = {'User-Agent': USER_AGENT}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, 'html.parser')
        meta = soup.find('meta', property='og:image')
        if meta:
            img_url = meta['content']
            img_data = requests.get(img_url).content
            path = f"{DOWNLOAD_FOLDER}/pin_{chat_id}.jpg"
            with open(path, 'wb') as f:
                f.write(img_data)
            return path
        return None
    except Exception as e:
        print(f"Pinterest error: {e}")
        return None

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
@bot.message_handler(content_types=['text'])
def handle_urls(message):
    text = message.text
    cid = message.chat.id

    if "pinterest.com" in text or "pin.it" in text:
        bot.send_message(cid, "📌 Обрабатываю Pinterest...")
        file_path = get_pinterest_image(text, cid)
        if file_path:
            with open(file_path, 'rb') as f:
                bot.send_photo(cid, f)
            os.remove(file_path)
        else:
            bot.send_message(cid, "Не удалось скачать фото с Pinterest.")

    elif "instagram.com" in text:
        bot.send_message(cid, "📸 Обрабатываю Instagram (альбом)...")
        results = get_insta_content(text)
        
        if not results:
            bot.send_message(cid, "Ошибка доступа к Instagram. Проверьте ссылку или куки.")
            return

        try:
            if len(results) == 1:
                item = results[0]
                if item['is_video']:
                    bot.send_video(cid, item['url'])
                else:
                    bot.send_photo(cid, item['url'])
            else:
                # Создаем группу медиа (до 10 элементов)
                media_group = []
                for entry in results[:10]:
                    if entry['is_video']:
                        media_group.append(types.InputMediaVideo(entry['url']))
                    else:
                        media_group.append(types.InputMediaPhoto(entry['url']))
                
                bot.send_media_group(cid, media_group)
        except Exception as e:
            bot.send_message(cid, f"Ошибка отправки: {e}")
    
    else:
        bot.send_message(cid, "Пожалуйста, отправьте корректную ссылку на Instagram или Pinterest.")

# --- ЗАПУСК ---
if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    print("Бот запущен и готов к работе...")
    bot.infinity_polling()
