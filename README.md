# رادار فارسی اخبار اسپانیا — نسخه نهایی

این پکیج خبرهای رسانه‌های اسپانیایی را جمع‌آوری می‌کند، موارد تکراری را حذف می‌کند، با OpenAI به فارسی ترجمه و خلاصه می‌کند و خبرهای مهم را به کانال تلگرام می‌فرستد.

## امکانات

- داشبورد فارسی و واکنش‌گرا
- نمایش هم‌زمان ترجمه فارسی و تیتر اصلی اسپانیایی
- خلاصه فارسی و بخش «چرا مهم است؟»
- جمع‌آوری RSS از RTVE، EL PAÍS و La Vanguardia
- حذف خبر تکراری
- دسته‌بندی و امتیاز اهمیت
- قالب HTML مناسب تلگرام
- جلوگیری از ارسال دوباره با `data/posted.json`
- محدودیت تعداد ارسال در هر اجرا برای جلوگیری از بمباران کانال
- اجرای خودکار تقریباً هر ۳۰ دقیقه در GitHub Actions

## ۱. ساخت کانال و بات تلگرام

1. یک کانال عمومی یا خصوصی بسازید.
2. در `@BotFather` یک بات بسازید و Token را دریافت کنید.
3. بات را به‌عنوان **Administrator** کانال اضافه کنید و اجازه `Post Messages` بدهید.
4. نام کاربری کانال مانند `@SpainNewsFA` را نگه دارید.

## ۲. تنظیم Secrets در GitHub

در Repository به مسیر `Settings → Secrets and variables → Actions` بروید و این Secrets را بسازید:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID` — مانند `@SpainNewsFA`

## ۳. تنظیم لینک کانال

در فایل `config.js` مقدار زیر را تغییر دهید:

```js
telegramChannelUrl: "https://t.me/SpainNewsFA"
```

## ۴. فعال‌سازی GitHub Actions و Pages

1. در `Settings → Actions → General`، گزینه **Read and write permissions** را فعال کنید.
2. Workflow با نام **Update, translate and publish** را یک بار دستی اجرا کنید.
3. در `Settings → Pages`، انتشار را از شاخه `main` و پوشه `/root` فعال کنید.

## ۵. تست محلی

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="..."
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHANNEL_ID="@YourChannel"

python scripts/pipeline.py
python -m http.server 8000
```

در ویندوز به‌جای `export` از `$env:NAME="..."` در PowerShell استفاده کنید.

## کنترل انتشار

در Workflow:

- `TELEGRAM_MIN_PRIORITY`: حداقل امتیاز ارسال
- `TELEGRAM_MAX_POSTS`: حداکثر پست در هر اجرا
- `MAX_AI_TRANSLATIONS`: سقف ترجمه‌های جدید هر اجرا
- `OPENAI_MODEL`: مدل ترجمه و خلاصه‌سازی

پیشنهاد شروع: ابتدا `TELEGRAM_MIN_PRIORITY` را روی `90` و `TELEGRAM_MAX_POSTS` را روی `1` بگذارید، سپس بعد از بررسی خروجی آن را کاهش دهید.

## نکات مهم

- Secretها را هرگز داخل فایل‌ها commit نکنید.
- شرایط استفاده و حق نشر رسانه‌های منبع را رعایت کنید.
- ترجمه ماشینی ممکن است خطا داشته باشد؛ لینک اصلی همیشه حفظ شده است.
- آدرس RSS رسانه‌ها ممکن است تغییر کند.
