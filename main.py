import telebot
import os
import requests
from bs4 import BeautifulSoup
import instaloader
import re
import shutil
import http.cookiejar
import json
from flask import Flask
from threading import Thread
from telebot import types

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
COOKIE_FILE = 'cookies.txt'

bot = telebot.TeleBot(BOT_TOKEN)
L = instaloader.Instaloader(user_agent=USER_AGENT)

# --- FLASK СЕРВЕР (Оригинальная структура) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running via Cookies with Carousel support!", 200

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
            cj = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
            cj.load(ignore_discard=True, ignore_expires=True)
            L.context._session.cookies.update(cj)
            L.context._session.headers.update({'User-Agent': USER_AGENT})
            username = L.test_login()
            if username:
                print(f"Instagram: авторизован как {username}")
        except Exception as e:
            print(f"Instagram Auth Error: {e}")

setup_instagram()

# --- ЛОГИКА ИЗВЛЕЧЕНИЯ КОНТЕНТА ---

def get_pinterest_content(url):
    try:
        headers = {'User-Agent': USER_AGENT}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, 'html.parser')
        script_tag = soup.find('script', id='__PWS_DATA__')
        
        images = []
        if script_tag:
            try:
                data = json.loads(script_tag.string)
                # Пытаемся найти изображения в структуре Story Pin (Idea Pin)
                pins = data.get('props', {}).get('initialReduxState', {}).get('pins', {})
                for pin_id in pins:
                    pin_data = pins[pin_id]
                    # Проверяем наличие страниц карусели
                    story_pages = pin_data.get('story_pin_data', {}).get('pages', [])
                    if story_pages:
                        for page in story_pages:
                            img_url = page.get('blocks', [{}])[0].get('image', {}).get('images', {}).get('originals', {}).get('url')
                            if img_url: images.append({'url': img_url, 'is_video': False})
                    
                    # Если страниц нет, берем основное фото
                    if not images:
                        main_img = pin_data.get('images', {}).get('orig', {}).get('url')
                        if main_img: images.append({'url': main_img, 'is_video': False})
            except:
                pass

        # Резервный вариант через OpenGraph, если JSON не отдался
        if not images:
            meta_img = soup.find('meta', property='og:image')
            if meta_img: images.append({'url': meta_img['content'], 'is_video': False})
            
        return images if images else None
    except Exception as e:
        print(f"Pinterest Error: {e}")
        return None

def get_tiktok_content(url):
    try:
        api_url = f"https://www.tikwm.com/api/?url={url}"
        response = requests.get(api_url).json()
        data = response.get('data')
        if not data: return None
        
        if 'images' in data and data['images']:
            return [{'url': img, 'is_video': False} for img in data['images']]
        if 'play' in data:
            return [{'url': data['play'], 'is_video': True}]
        return None
    except Exception as e:
        print(f"TikTok Error: {e}")
        return None

def get_insta_content(url):
    try:
        match = re.search(r'/(p|reel|tv)/([^/?#&]+)', url)
        if not match: return None
        post = instaloader.Post.from_shortcode(L.context, match.group(2))
        
        if post.typename == 'GraphSidecar':
            return [{'url': n.video_url if n.is_video else n.display_url, 'is_video': n.is_video} for n in post.get_sidecar_nodes()]
        return [{'url': post.video_url if post.is_video else post.url, 'is_video': post.is_video}]
    except Exception as e:
        print(f"Instagram Error: {e}")
        return None

# --- ОБРАБОТЧИК ---

def process_media_results(chat_id, results):
    if not results:
        bot.send_message(chat_id, "Не удалось извлечь контент. Возможно, пост приватный или ссылка битая.")
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
                if i >= 10: break
                if entry['is_video']:
                    media_group.append(types.InputMediaVideo(entry['url']))
                else:
                    media_group.append(types.InputMediaPhoto(entry['url']))
            bot.send_media_group(chat_id, media_group)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка отправки: {e}")

@bot.message_handler(content_types=['text'])
def handle_message(message):
    url = message.text
    cid = message.chat.id
    
    if "pinterest.com" in url or "pin.it" in url:
        bot.send_message(cid, "Pinterest: собираю все фото...")
        process_media_results(cid, get_pinterest_content(url))

    elif "instagram.com" in url:
        bot.send_message(cid, "Instagram: извлекаю медиа...")
        process_media_results(cid, get_insta_content(url))

    elif "tiktok.com" in url:
        bot.send_message(cid, "TikTok: качаю...")
        process_media_results(cid, get_tiktok_content(url))
    else:
        bot.send_message(cid, "Пришлите ссылку на Instagram, Pinterest или TikTok.")

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    print("Бот запущен с полной поддержкой каруселей!")
    bot.infinity_polling()
