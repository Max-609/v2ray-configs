# main.py

import os
import logging
import requests
from bs4 import BeautifulSoup
import jdatetime
import locale
import time
from telegram import Update, Bot
from flask import Flask, request
import asyncio

# --- تنظیمات اصلی که از گوگل کلاد خوانده می‌شود ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TARGET_CHANNEL_ID")
SCHEDULER_SECRET = os.environ.get("SCHEDULER_SECRET") # یک کلمه عبور مخفی برای ساعت زنگ‌دار
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # آدرس ربات شما در گوگل کلاد

# --- بقیه کدها (بخش دریافت قیمت بدون تغییر) ---
# ... (تمام توابع get_prices و format_number را از کد قبلی خود اینجا کپی کنید) ...
# ... (تابع get_prices شما کاملاً خوب بود، پس نیازی به تغییرش نیست) ...
def format_number(num):
    if isinstance(num, (int, float)):
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            return locale.format_string("%d", num, grouping=True)
        except locale.Error:
            return f"{num:,}"
    return num

def get_prices():
    prices = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    rial_pages = {
        'usd': ("https://www.tgju.org/profile/price_dollar_rl", 10), 'eur': ("https://www.tgju.org/profile/price_eur", 10),
        'usdt': ("https://www.tgju.org/profile/crypto-tether", 0), 'ounce': ("https://www.tgju.org/profile/ons", 0),
        'gold_18': ("https://www.tgju.org/profile/geram18", 10), 'gold_24': ("https://www.tgju.org/profile/geram24", 10),
    }
    for name, (url, divisor) in rial_pages.items():
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            element = soup.select_one('span.price')
            if element:
                price_text = element.text.strip().replace(',', '')
                prices[name] = price_text if divisor == 0 else format_number(int(price_text) // divisor)
            else: prices[name] = 'N/A'
            time.sleep(0.3)
        except: prices[name] = 'N/A'
    try:
        crypto_data = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=15).json()
        crypto_map = {item['symbol']: float(item['price']) for item in crypto_data}
        wanted_cryptos = {'btc': 'BTCUSDT', 'eth': 'ETHUSDT', 'trx': 'TRXUSDT', 'sol': 'SOLUSDT', 'ton': 'TONUSDT', 'xrp': 'XRPUSDT'}
        for name, symbol in wanted_cryptos.items():
            if symbol in crypto_map:
                price_val = crypto_map[symbol]
                prices[name] = f"{price_val:.4f}" if price_val < 10 else format_number(int(price_val))
            else: prices[name] = 'N/A'
    except:
        for name in wanted_cryptos.keys(): prices[name] = 'N/A'
    return prices

# --- تابع ارسال پیام به کانال ---
async def send_price_update(bot: Bot):
    all_prices = get_prices()
    now = jdatetime.datetime.now()
    message = f"""
🔸🔹 **قیمت‌های لحظه‌ای بازار** 🔹🔸
💵 دلار: `{all_prices.get('usd', 'N/A')}` ت
💶 یورو: `{all_prices.get('eur', 'N/A')}` ت
💲 تتر: `{all_prices.get('usdt', 'N/A')}` ت
---
🔶 بیت‌کوین: `{all_prices.get('btc', 'N/A')}` $
🔶 اتریوم: `{all_prices.get('eth', 'N/A')}` $
---
🌟 انس جهانی: `{all_prices.get('ounce', 'N/A')}` $
💍 طلای ۱۸: `{all_prices.get('gold_18', 'N/A')}` ت
---
📅 `{now.strftime("%Y/%m/%d - %H:%M")}`
"""
    await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode='Markdown')
    logging.info("Price update sent.")

# --- راه‌اندازی وب‌سرور با Flask ---
app = Flask(__name__)
bot = Bot(token=TOKEN)

# این آدرس توسط "ساعت زنگ‌دار" گوگل صدا زده می‌شود
@app.route(f"/trigger/{SCHEDULER_SECRET}", methods=["POST"])
async def trigger_by_scheduler():
    await send_price_update(bot)
    return "OK"

# این آدرس توسط تلگرام برای ارسال پیام کاربران صدا زده می‌شود
@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook_handler():
    update = Update.de_json(request.get_json(force=True), bot)
    # اینجا می‌توانید دستورات ربات (مثل /start) را مدیریت کنید
    return "OK"

# یک صفحه ساده برای اینکه ببینیم ربات کار می‌کند
@app.route("/")
def index():
    return "I'm alive!"

# در اولین اجرای برنامه، آدرس ربات را به تلگرام معرفی می‌کنیم
if WEBHOOK_URL and TOKEN:
    asyncio.run(bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}"))
    logging.info(f"Webhook set to {WEBHOOK_URL}/{TOKEN}")