# بررسی دسترسی انتشار پیش‌نمایش — ۲۰۲۶-۱۰-۲۹

مرجع تصمیم‌ها Vault، به‌ویژه `META-INT-140` v0.7.0 است؛ این گزارش تصمیم معماری جدید نیست. ساعت محیط و GitHub تاریخ متفاوتی نشان داده و اختلاف هنوز تأیید نشده است.

## شواهد

- [PR #21](https://github.com/feerozmandi/xennic-website/pull/21) با merge commit `09a9d00f25cee181a24fa39d645256869b6dc221` ادغام شد. [انتشار run 151](https://github.com/feerozmandi/xennic-website/actions/runs/42642887548) و [verifier مستقل](https://github.com/feerozmandi/xennic-website/actions/runs/42645113218/job/129256180630) برای digest `sha256:9e70bfceebafb0dd83152fb09f2e4d34b2e109497c34a1dad827e5046a31071f` موفق بودند. verifier از credential موقت runner استفاده کرد.
- مالک ارتقای محدود helper و بررسی پیکربندی، backup policy، gateway preflight و pull همان digest روی VPS را موفق گزارش کرد. این‌ها به معنای استقرار یا ورود واقعی نیستند. نتیجهٔ دریافت artifact بی‌نام از VPS هنوز نرسیده است.
- آزمون verifier بی‌نام واقعی در [CI 42661769448](https://github.com/feerozmandi/xennic-website/actions/runs/42661769448/job/129314894058) به HTTP 401 در endpoint دانلود artifact رسید، با وجود موفقیت بررسی tip؛ دریافت بی‌نام شاهد در آن runner ممکن نشد. پاسخ 302 مشاهده‌شده در Sandbox به‌تنهایی اثبات دانلود نبود. آزمون موقت برداشته شد، نه اینکه موفق تلقی شود؛ verifier اصلی با credential معتبر و کنترل‌های provenance و redirect حفظ شده است.
- ساخت Environment `preview` با دسترسی اتصال موجود GitHub با 403 متوقف شد؛ از مالک ایجاد محیط محدود به شاخهٔ `dev` بدون افزودن secret درخواست شده است. نتیجه هنوز نرسیده است.

## تغییر محدود پیشنهادی

برای package عمومی، مقدار غیرمحرمانهٔ صریح `public-read` فقط در عملیات pull موجب استفاده از Docker config خالی و بدون login می‌شود؛ digest و معماری همچنان بررسی می‌شوند. backend پیشنهادی credential API را به pull ارسال نمی‌کند؛ شکست pull عمومی متوقف می‌کند و به credential API یا روش دیگری fallback نمی‌کند. دسترسی API و GHCR مستقل‌اند؛ در صورت خصوصی‌شدن GHCR باید دسترسی مستقل آن طراحی و تأیید شود. credential اشتباه در مسیر احراز هویت pull همچنان باعث شکست است و fallback بی‌نام ندارد. نام محیط قدیمی client (`PREVIEW_GHCR_TOKEN`) برای سازگاری حفظ شده اما در backend پیشنهادی فقط credential API را حمل می‌کند؛ ورود هیچ مقدار واقعی در Git یا گفتگو مجاز نیست.

آزمون واحد محلی با پاسخ‌های مصنوعی موفق بود؛ آزمون pull بی‌نام digest منتشرشده برای publication بعدی در CI تعریف شده است و نتیجهٔ CI نسخهٔ نهایی هنگام نگارش باز است. هیچ‌یک جایگزین آزمون VPS نیست. این تغییر به‌تنهایی دستور استقرار، راه‌اندازی سرویس یا upgrade روی VPS نیست؛ installer موجود هنوز مسیر ارتقا از نسخهٔ نصب‌شدهٔ `09a9d00` به این نامزد را فراهم نمی‌کند. backend و receiver همچنان غیرفعال‌اند. پس از آماده‌شدن مسیر ایمن، امکان استفاده از credential کوتاه‌عمر و فقط‌خواندنی Actions برای API بدون ایجاد credential بلندمدت جداگانه باید عملیاتی آزموده شود.

## پیگیری و ریسک

تکمیل و آزمون محدود activation، نصب/ارتقای محافظت‌شده، کلید SSH محدود و workflow وابسته به محیط، verifier نوک dev بعد از هر merge، backup/restore واقعی و نخستین استقرار تحت نظارت باقی‌اند. DNS، HTTPS و OAuth واقعی و پذیرش دو دستگاه اثبات نشده‌اند. انتقال و restore واقعی backup محلی age به رایانه هنوز اثبات نشده؛ پیش از production به مقصد خودکار خارج VPS نیاز است. تغییرات و ابهام‌های مؤثر باید در نشست مستقل Vault پیگیری شوند؛ در این نشست Vault تغییر نکرد.
