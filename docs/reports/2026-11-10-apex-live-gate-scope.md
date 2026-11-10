# استقرار واقعی دامنهٔ اصلی و اصلاح scope گیت

- **تاریخ ثبت:** ۲۰۲۶-۱۱-۱۰ (ساعت سرور). ساعت محیط توسعه و GitHub با این تاریخ اختلاف دارد و اختلاف تأیید نشده است.
- **دامنهٔ تغییر این گزارش:** گذار لبه به `xennic.ir`، اولین استقرار واقعی روی VPS، بررسی HTTPS عمومی، و اصلاح سیاست scope گیت. جزئیات سرویس‌های موجود، n8n، بله و Open Notebook دست‌نخورده‌اند.

## ۱) گذار لبه به دامنهٔ اصلی (اجرا شد)

مالک اسکریپت نصب را در هر دو مسیر نصب کرد و پس از دروازهٔ هش، `--upgrade-apex` را اجرا کرد:

- پیام موفق: `Public edge switched to the approved apex; originals preserved; no deployment started.` با `exit=0`.
- هش فایل‌های نصب‌شده پس از گذار: `Caddyfile` = `462370b1…062f2`، `routes.caddy` = `a4d844df…4029`، `gateway.yml` = `1444baea…833ed` — دقیقاً همان نسخهٔ بازبینی‌شده.
- پیش از اجرا، pre-check فقط‌خواندنی `READY=PASS` و `HELPERS=TARGET:PASS ALIASES:PASS` را گزارش کرد.

دو تلاش قبلی به‌دلیل خطای خود اسکریپت (نه وضعیت سرور) شکست خوردند و هیچ فایلی تغییر نکرد:

1. مقایسهٔ helperها با مجموعه‌ای که receiver را هم شامل می‌شد → اصلاح در PR #28.
2. بارگذاری گارد سیاست از نسخهٔ نصب‌شدهٔ قدیمی که پارامتر `authority` را نمی‌شناخت → اصلاح در PR #29 (اعتبارسنجی هر دو سیاست با گارد همان بستهٔ staging).

## ۲) اولین استقرار (اجرا شد)

زنجیرهٔ محدود `release-check → migrate → activate → health` با توکن کوتاه‌عمر که مالک خودش ساخت و در فایل ریشه‌ای `0600` گذاشت اجرا شد:

- commit `da6487b626c163092e33fd576f04594fb6fe7f97`، run `198`، digest تأییدشدهٔ مستقل `sha256:d97511e3d0d288ab723d818c2b182c9212e874425e1d9c728a00551ada645109` (`linux/amd64`).
- خروجی: `Preview deployment completed; verify release status.` با `exit=0`.
- journal: `{"blocked":false,…,"last_run":198,"pending":null,"previous":[]}`.
- کانتینرها: `xennic-preview-app-1` (healthy)، `xennic-preview-postgres-1` (healthy)، `xennic-preview-gateway-caddy-1`، `xennic-preview-gateway-gate-1`؛ شش کانتینر `xennic-infra-*` بدون تغییر.
- تنها سرویس منتشرشده روی میزبان Caddy است؛ `80/tcp` و `443/tcp` روی `0.0.0.0` منتشر شده‌اند.

## ۳) شواهد عمومی HTTPS

- `http://xennic.ir/` → `308` به `https://xennic.ir/`.
- `https://xennic.ir/` → `200` با گواهی معتبر (`ssl_verify_result=0`) و عنوان `<title>Xennic</title>`.
- `https://xennic.ir/admin` → `302` به مسیر ورود گیت.
- `https://xennic.ir/api/globals/navigation` بدون نشست → `401` (شاخهٔ API عمداً redirect نمی‌کند).

این شواهد فقط صفحهٔ عمومی، گواهی و بسته‌بودن مسیرهای خصوصی را ثابت می‌کنند؛ ورود واقعی مدیریت هنوز برقرار نشده است.

## ۴) تشخیص شکست ورود OAuth

مالک پس از ورود GitHub صفحهٔ `Sign-in could not be completed` و در شبکه پاسخ `500` را گزارش کرد. زنجیرهٔ تشخیص، بدون افشای راز:

1. آزمون اعتبارنامه با کد جعلی: GitHub پاسخ `bad_verification_code` داد، نه `incorrect_client_credentials` ⇒ `client_id`/`client_secret` و `redirect_uri` ثبت‌شده سالم‌اند.
2. نمونهٔ تشخیصی خارج از گیت با همان فایل سیاست و لاگ مجاز نشان داد `oauth2-proxy v7.15.5` هر خطای تبادل کد را به همان صفحهٔ عمومی `500` تبدیل می‌کند.
3. آزمون اوراکل روی کد واقعی callback: `bad_verification_code` ⇒ کد پیش‌تر توسط گیت مصرف شده بود، یعنی تبادل انجام شده و شکست در مرحلهٔ **پس از** تبادل است.
4. در کد همان نسخه، `EnrichSession` پرووایدر GitHub **بی‌قید** ابتدا `getOrgAndTeam()` را صدا می‌زند و `/user/orgs` را می‌خواند؛ این درخواست به scope `read:org` نیاز دارد. سیاست بازبینی‌شده `scope = "user:email"` داشت، پس پاسخ ۴۰۳ و سپس ۵۰۰ رخ می‌داد. این رفتار در `v7.6.0` هم همین است؛ کاهش نسخه راه‌حل نیست و scope پیش‌فرض خود پروژه برای GitHub `user:email read:org` است.

مالک افزایش scope به `user:email read:org` را صریحاً تأیید کرد. این scope فقط فهرست سازمان‌های همان کاربر را می‌خواند و به مخزن، کد یا داده دسترسی اضافه نمی‌کند.

## ۵) تغییرات این PR

- `scripts/preview-fixed-operations.py`: سیاست ثابت گیت اکنون `scope = "user:email read:org"` را الزام می‌کند؛ هر مقدار دیگر رد می‌شود.
- `scripts/install-preview-sftp-helper.py`:
  - `_toml_value` فاصلهٔ داخلی رشته را می‌پذیرد (برای scope چندمقداری) ولی نقل‌قول، escape و کاراکتر کنترلی را رد می‌کند.
  - مرحلهٔ `--upgrade-scope` و `--rollback-scope`: تأیید helperهای نصب‌شده با manifest، تأیید اینکه فایل سیاست نصب‌شده **فقط** در یک مقدار canonical با نسخهٔ جدید تفاوت دارد (بازگرداندن همان خط باید بایت‌به‌بایت فایل اصلی را بسازد)، اعتبارسنجی با گارد همان بستهٔ staging و authority مشتق‌شده از هش `Caddyfile`، پشتیبان‌گیری از helperها و سیاست، جابه‌جایی اتمی و rollback.
- `scripts/preview-scope-precheck.py`: بررسی فقط‌خواندنی پیش از اجرا (helperها، سیاست، staging، نبود پشتیبان قبلی) با خروجی `READY=PASS/STOP`.
- `tests/preview-installer-scope.py`: ۹ آزمون واحد برای سیاست جدید، گذار تک‌مقداری، رد drift و فایل غیر‌canonical، و نگاشت authority.
- به‌روزرسانی fixtureهای موجود (`tests/preview-installer-apex.py`، `tests/preview-network-topology.py`، `tests/preview-sftp-installed-ci.sh`) با scope جدید.

## ۶) فعال‌سازی سیاست جدید و ورود واقعی (انجام شد)

- پس از اجرای موفق `--upgrade-scope`، journal و ایمیج دست‌نخورده ماندند؛ فقط کانتینر `gate` با همان ایمیج و همان فایل سیاست بازایجاد شد
  (`docker compose --project-name xennic-preview-gateway … up -d --no-deps --force-recreate --no-build --pull never gate`, `exit=0`).
- Caddy، اپ، PostgreSQL و شش کانتینر `xennic-infra-*` بازایجاد نشدند.
- مالک ورود به `https://xennic.ir/admin` با حساب مجاز GitHub را **موفق** گزارش کرد؛ این نخستین شاهد واقعی پذیرش OAuth و نشست گیت روی دامنهٔ اصلی است.
- تلاش برای استقرار کامل run `203` پیش از این مرحله با پیام عمومی `Preview deployment blocked or failed` متوقف شد و هیچ نوشتنی انجام نداد؛ علت قابل‌انتظار، نبود رکورد بازبینی‌شدهٔ گذار مهاجرت و backup تأییدشده برای ارتقای یک استقرار موجود است. آن مسیر برای ارتقای ایمیج لازم است و به‌صورت جداگانه آماده می‌شود.

## ۷) ریسک‌ها و کارهای باز

- **مسیر ارتقای ایمیج هنوز آزموده نشده است:** برای هر استقرار بعدی روی همین نصب، زنجیره به `config/compatible-transitions.json` بازبینی‌شده و `state/backup-<run>.json` همراه با `work/backup.age` تأییدشده نیاز دارد. این کارها انجام نشده‌اند؛ استقرار فعلی (run 198) عوض نشد.
- **بازایجاد دستی gate:** چون تغییر فقط یک مقدار پیکربندی بود، gate بدون استقرار بازایجاد شد؛ این کار عمداً محدود و مستند است و برای تغییرات ایمیج یا داده تکرار نمی‌شود.
- **لاگ گیت خاموش است** (گارد بازبینی‌شده `LogConfig=none` را الزام می‌کند). بنابراین تشخیص آیندهٔ خطاهای ورود بدون روشن‌کردن بازبینی‌شدهٔ لاگ ممکن نیست؛ این گزارش چیزی از آن گارد را تغییر نمی‌دهد.
- **backup خارج VPS و restore** هنوز اثبات نشده است؛ ادعای مالک دربارهٔ گرفتن backup توسط پشتیبانی بدون شاهد مستقل است.
- **واگرایی Vault §۱۰:** مرجع فعلی فقط preview خصوصی را مجاز می‌داند و دامنهٔ اصلی را مستثنی می‌کند؛ تصمیم مالک بر HTTPS عمومی `xennic.ir` است و این اختلاف باید در نشست مستقل Vault ثبت و حل شود. این نشست Vault را فقط خوانده است.
- **پورت‌های لبه:** Caddy روی `0.0.0.0` منتشر می‌شود؛ محدودکردن آن به IP عمومی نیازمند انتشار و گذار تازه است و فعلاً انجام نشده.
