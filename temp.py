import requests
from bs4 import BeautifulSoup
import jdatetime
import locale
import logging
import time
from telegram import Update
from telegram.ext import Application, ContextTypes

# ===============================================================
# بخش تنظیمات: مقادیر زیر را با اطلاعات خودتان پر کنید
# ===============================================================

# ۱. توکن رباتی که از BotFather دریافت کرده‌اید
TELEGRAM_BOT_TOKEN = "8063893101:AAGRUAHM6-Iy0_qoPUqmmyuqohCq2YFb3tY" 

# ۲. شناسه عددی کانال مورد نظر (معمولا با -100 شروع می‌شود)
TARGET_CHANNEL_ID = -1002697577898 

# ===============================================================

# تنظیمات لاگ برای نمایش خطاها و وضعیت در ترمینال
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# تنظیمات قالب‌بندی اعداد برای جداکننده هزارگان
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, '') # استفاده از تنظیمات پیش‌فرض سیستم

def format_number(num):
    """یک عدد را با جداکننده هزارگان (کاما) فرمت‌بندی می‌کند"""
    if isinstance(num, (int, float)):
        return locale.format_string("%d", num, grouping=True)
    return num # اگر ورودی عدد نباشد (مثلا 'N/A')، آن را برمی‌گرداند

def get_prices():
    """
    از دو منبع استفاده می‌کند:
    1. صفحات داخلی و جداگانه tgju.org برای هر ارز و طلا (روش پایدار)
    2. بایننس برای ارزهای دیجیتال
    """
    prices = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    # --- بخش اول: دریافت قیمت ارز و طلا از صفحات داخلی tgju.org ---
    
    # دیکشنری برای آدرس صفحات هر قیمت
    rial_pages = {
        'usd': ("https://www.tgju.org/profile/price_dollar_rl", 10),
        'eur': ("https://www.tgju.org/profile/price_eur", 10),
        'usdt': ("https://www.tgju.org/profile/crypto-tether", 0),
        'ounce': ("https://www.tgju.org/profile/ons", 0),
        'gold_18': ("https://www.tgju.org/profile/geram18", 10),
        'gold_24': ("https://www.tgju.org/profile/geram24", 10),
    }

    for name, (url, divisor) in rial_pages.items():
        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # شناسه قیمت در تمام این صفحات یکسان و پایدار است
            element = soup.select_one('span.price')
            
            if element:
                price_text = element.text.strip().replace(',', '')
                if divisor == 0: # برای انس جهانی که رشته است
                    prices[name] = price_text
                else:
                    prices[name] = format_number(int(price_text) // divisor)
            else:
                prices[name] = 'N/A'
            
            # یک وقفه کوتاه برای جلوگیری از بلاک شدن توسط سایت
            time.sleep(0.5)

        except Exception as e:
            logging.error(f"Error fetching {name} from {url}: {e}")
            prices[name] = 'N/A'
            
    logging.info("Finished fetching Toman/Rial prices from individual tgju.org pages.")

    # --- بخش دوم: دریافت قیمت ارزهای دیجیتال از API بایننس (بدون تغییر) ---
    try:
        binance_url = "https://api.binance.com/api/v3/ticker/price"
        response = requests.get(binance_url, timeout=20)
        response.raise_for_status()
        crypto_data = response.json()

        crypto_map = {item['symbol']: float(item['price']) for item in crypto_data}
        
        wanted_cryptos = {
            'btc': 'BTCUSDT', 'eth': 'ETHUSDT', 'trx': 'TRXUSDT',
            'sol': 'SOLUSDT', 'ton': 'TONUSDT', 'xrp': 'XRPUSDT',
            'bnb': 'BNBUSDT'
        }

        for name, symbol in wanted_cryptos.items():
            if symbol in crypto_map:
                price_val = crypto_map[symbol]
                if price_val < 10:
                    prices[name] = f"{price_val:.4f}"
                else:
                    prices[name] = format_number(int(price_val))
            else:
                prices[name] = 'N/A'
        logging.info("Successfully fetched crypto prices from Binance API")

    except Exception as e:
        logging.error(f"Error fetching from Binance API: {e}")
        for name in wanted_cryptos.keys():
            prices[name] = 'N/A'
            
    return prices


async def send_periodic_prices(context: ContextTypes.DEFAULT_TYPE) -> None:
    """این تابع به صورت زمان‌بندی شده برای ارسال پیام به کانال اجرا می‌شود."""
    logging.info("Fetching prices for the channel...")
    all_prices = get_prices()
    now = jdatetime.datetime.now()
    jalali_date = now.strftime("%Y/%m/%d")
    jalali_time = now.strftime("%H:%M")

    # توجه: واحد ارزهای دیجیتال به "تومان" تغییر کرده است
    message = f"""
🔸🔹 **قیمت‌های لحظه‌ای بازار ارز و طلا** 🔹🔸

💱 **ارزهای خارجی:**
      💵 دلار آمریکا: `{all_prices.get('usd', 'N/A')}` تومان
      💶 یورو اروپا: `{all_prices.get('eur', 'N/A')}` تومان

🪙 **ارزهای دیجیتال (به دلار):**
      🔶 بیت‌کوین: `{all_prices.get('btc', 'N/A')}` دلار
      🔶 اتریوم: `{all_prices.get('eth', 'N/A')}` دلار
      🔶 ترون: `{all_prices.get('trx', 'N/A')}` دلار
      🔶 سولانا: `{all_prices.get('sol', 'N/A')}` دلار
      🔶  تون کوین: `{all_prices.get('ton', 'N/A')}` دلار
      🔶 ریپل: `{all_prices.get('xrp', 'N/A')}` دلار
      💲 تتر (USDT): `{all_prices.get('usdt', 'N/A')}` دلار

✨ **طلا:**
      🌟 انس جهانی: `{all_prices.get('ounce', 'N/A')}` دلار
      💍 طلای ۱۸ عیار: `{all_prices.get('gold_18', 'N/A')}` تومان
      🏆 طلای ۲۴ عیار: `{all_prices.get('gold_24', 'N/A')}` تومان

📅 تاریخ: `{jalali_date} - {jalali_time}`
    """
    print(message)
    try:
        await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=message, parse_mode='Markdown')
        logging.info(f"Price update successfully sent to channel {TARGET_CHANNEL_ID}")
    except Exception as e:
        logging.error(f"Failed to send message to channel {TARGET_CHANNEL_ID}: {e}")
        
        
def main() -> None:
    """ربات را راه‌اندازی کرده و کار زمان‌بندی شده را اجرا می‌کند."""
    # ۱. ساخت اپلیکیشن ربات
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ۲. دسترسی به Job Queue
    job_queue = application.job_queue

    # ۳. بررسی وجود Job Queue و تعریف کار تکرارشونده
    if job_queue:
        job_queue.run_repeating(send_periodic_prices, interval=60, first=10)
        logging.info("Scheduled job started. The bot will send updates every 10 minutes.")
    else:
        # این بخش در حالت عادی هرگز اجرا نمی‌شود
        logging.error("Job Queue is not available, could not schedule the task.")
        return

    logging.info("Bot is running... Press Ctrl+C to stop.")
    
    # ۴. شروع به کار ربات
    application.run_polling()
if __name__ == "__main__":
    main()
