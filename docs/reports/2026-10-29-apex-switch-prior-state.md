# گزارش: تصحیح گذار لبه بر پایهٔ وضعیت واقعی نصب‌شده

- **تاریخ گزارش:** ۲۰۲۶-۱۰-۲۹ (تاریخ محیط GitHub هنوز تأیید نشده است).
- **مبنا:** dev `25f4b87b69b897b81bd8f51efeb09f3e00a5ec03` (PR #26 ادغام‌شده) و خروجی pre-check مالک روی سرور.
- **وضعیت:** گذار تصحیح و محلی آزموده شد؛ روی VPS اجرا نشده است.

## یافته‌ها از pre-check مالک

| خط خروجی | معنا |
|---|---|
| `STATE=EMPTY WORK=EMPTY JOURNAL=ABSENT` | وضعیت پیش از استقرار اول؛ شرط لازم گذار برقرار است |
| `EDGE=… routes.caddy:FAIL` | **واقعی:** نسخهٔ نصب‌شدهٔ سرور release `09a9d00` است و `routes.caddy` آن (`d089cbb6…`) هنوز مسیرهای عمومی apex را ندارد. مسیرهای حاوی apex (`a4d844df…`) بخشی از همان انتشار نبودند. |
| `HELPERS=TARGET:FAIL` | **خطای pre-check، نه سرور:** نسخهٔ اول pre-check نام فایل‌های helper را خام بررسی می‌کرد، در حالی که نصب واقعی برای چهار فایل از نام‌های اجرایی ثابت استفاده می‌کند (`sftp-transfer`، `pull-image`، `backup-verify` و شش alias گارد). |
| خطای `incoming-apex/preview-backup-sftp.py` | staging ناقص ماند؛ بلوک کپی پیش از تکمیل متوقف شده بود (احتمالاً به‌دلیل `set -e`). |

نتیجه: گذار قبلی دو فرض غلط داشت — `routes.caddy` را از پیش بازبینی‌شده می‌گرفت و نسخهٔ helper نصب‌شده را کامل بررسی نمی‌کرد.

## اصلاحات

- **وضعیت پیشین pin شد:** helperهای نصب‌شده با جدول هش دقیق release `09a9d00` (`PRIOR_HELPERS`) و پنج فایل config با هش‌های همان انتشار بررسی می‌شوند؛ نام‌های نصب‌شده دقیقاً برابر مجموعهٔ انتظار باید باشند.
- **گذار اکنون `routes.caddy` را هم نصب می‌کند** (`a4d844df…`) تا مسیرهای عمومی apex وجود داشته باشند، همراه با `Caddyfile` و `gateway.yml` apex و سیاست OAuth و origin.
- **پنج فایل و مجموعهٔ helper اتمی جابه‌جا می‌شوند**، نسخه‌های قبلی در `config/.apex-before/` و `/usr/local/libexec/.xennic-preview-before-apex` نگه داشته می‌شوند و هر خطا همه را برمی‌گرداند. `--rollback-apex` همهٔ پنج فایل و helperها را بازمی‌گرداند.
- **`scripts/preview-apex-precheck.py`** اضافه شد: فقط‌خواندنی، root، بدون چاپ secret؛ برای هر شرط `PASS/FAIL` و در پایان `READY=PASS` یا `READY=STOP` می‌دهد.

## تصحیح دوم pre-check

اجرای واقعی روی سرور نشان داد pre-check مجموعهٔ helper نصب‌شده را با `deploy-receiver` مقایسه می‌کند، در حالی که این فایل را خودِ گذار نصب می‌کند. مقایسه اکنون فقط شامل مجموعهٔ پیشین است و در صورت اختلاف، نام فایل‌های کم/اضافه را چاپ می‌کند؛ با یک فایل اضافی، خروجی `READY=STOP` و با وضعیت درست `READY=PASS` است.

## تصحیح سوم: بارگذاری alias بدون پسوند

اجرای واقعی `--upgrade-apex` با `AttributeError: 'NoneType' object has no attribute 'loader'` متوقف شد: `importlib` برای فایل‌های نصب‌شده‌ای که پسوند `.py` ندارند (`release-check` و سایر aliasها) spec نمی‌سازد. تابع `module()` در installer اکنون `SourceFileLoader` را صریح می‌سازد و برای هر دو حالت آزمون دارد. این شکست در مرحلهٔ بارگذاری گارد رخ داد، یعنی **پیش از هر نوشتن**؛ هش هر سه فایل config پس از اجرا همان نسخهٔ preview باقی ماند.

## تصحیح چهارم: اعتبارسنجی با گارد همان نسخه

پس از اصلاح alias، گذار در `TypeError: validate_gateway_oauth() got an unexpected keyword argument 'authority'` متوقف شد: سیاست جدید با گارد **نصب‌شده** (release `09a9d00`) اعتبارسنجی می‌شد که پارامتر authority را ندارد. گذار اکنون هر دو سیاست (preview فعلی و apex جدید) را با گارد و readiness موجود در بستهٔ staging اعتبارسنجی می‌کند و یک تست تضمین می‌کند مسیر بارگذاری گارد همیشه همان نسخهٔ staging باشد. این شکست هم پیش از هر نوشتنی رخ داد و هش سه فایل config بدون تغییر ماند.

## آزمون‌ها

| آزمون | محیط | نتیجه |
|---|---|---|
| `tests/preview-installer-apex.py` | محلی | ۱۱ تست: گذار کامل، بازگردانی در خطای تزریقی، رد وضعیت ناشناخته و rollback |
| `tests/preview-network-topology.py` | محلی | ۱۸ تست موفق |
| `tests/preview-deploy-backend.py` | محلی | ۱۵ تست موفق |
| `tests/preview-deploy-readiness.py` | محلی | ۸ تست موفق |
| `scripts/preview-apex-precheck.py` | شبیه‌سازی ریشهٔ ساختگی | خروجی `READY=PASS` و رد موارد ناقص |
| CI شاخه | GitHub Actions | در انتظار نتیجه |

## گام بعدی پس از تأیید CI

staging کامل (۱۵ helper + installer + `incoming-apex` شامل `routes.caddy`) از tarball commit منتشرشده، اجرای `preview-apex-precheck.py` و سپس `--upgrade-apex`. اجرای مجدد یا میان‌بر دستی مجاز نیست.

## ریسک‌ها

- گذار همچنان فقط در وضعیت «پیش از استقرار اول» اجرا می‌شود؛ اگر journal یا state ظاهر شود متوقف می‌شود.
- ACME عمومی، ورود OAuth واقعی و دسترسی ورودی ۸۰/۴۴۳ همچنان آزموده نشده‌اند.
- محدودهٔ Vault §۱۰ هنوز preview خصوصی است و هم‌راستاسازی مدیریت لازم است.

## پیگیری Vault

`META-INT-140` §۱۰؛ Vault در این نشست فقط‌خواندنی بوده و تغییر نکرده است.
