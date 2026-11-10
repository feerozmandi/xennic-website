# ارتقای کنترل‌شدهٔ سایت زنده از run ۱۹۸ به run ۲۰۷

## چه شد

سایت عمومی روی `https://xennic.ir` با همان مسیر کنترل‌شدهٔ استقرار (readiness → verify helpers → release-check → pull → backup → migrate → activate → health) از نسخهٔ `da6487b` (run ۱۹۸) به نسخهٔ `a3a2316` (run ۲۰۷) ارتقا یافت. این ارتقا **آخرین کاری است که پیش از پیشرفت به مرحلهٔ ۲ لازم بود**؛ پیش از آن، رکورد تأییدشدهٔ گذار مهاجرت و پشتیبان تأییدشده آماده نبودند.

طراحی تازهٔ صفحهٔ اصلی، سربرگ و پابرگ (مرحلهٔ ۱) اکنون روی دامنهٔ اصلی در دسترس مالک است.

## مصنوعات تأییدشده

| مورد | مقدار |
|---|---|
| نسخهٔ قبلی | `da6487b626c163092e33fd576f04594fb6fe7f97` — run ۱۹۸ — `sha256:d97511e3d0d288ab723d818c2b182c9212e874425e1d9c728a00551ada645109` |
| نسخهٔ نامزد | `a3a2316ce6031c2ad6fb71b6231174b0ce4d4e30` — run ۲۰۷ (CI `42846562382`) — `sha256:4474049f29ef180704f2251353f2fe18abe743f735875bd30cf81ef2b6e9d57a` |
| هش درخت مهاجرت | `9f66a5faa171cd9a959a400b117d96d8a0832cfa69c27e9ba8cd76922632e69d` (پنج فایل `migrations/`) |
| Ledger پایگاه‌داده | تنها `20261030_163225_baseline` در batch ۱ |
| تفاوت مهاجرت‌ها بین دو کامیت | هیچ؛ از این رو `previous_migrations` فقط همان یک مقدار است |

هش درخت مهاجرت از blobهای همان کامیت محاسبه شد (فرمول `name\\0len\\0data` به ترتیب مرتب) و مقدار آن با ledger موجود تطبیق داده شد؛ هیچ مقداری حدس زده یا جعل نشد.

## رکورد گذار

فایل `/srv/xennic-preview/config/compatible-transitions.json` با مالکیت root و حالت `0600` ساخته شد و دقیقاً یک ردیف دارد:

```json
{"version": 1, "transitions": [{"from_commit": "da6487b626c163092e33fd576f04594fb6fe7f97", "to_commit": "a3a2316ce6031c2ad6fb71b6231174b0ce4d4e30", "migration_sha256": "9f66a5faa171cd9a959a400b117d96d8a0832cfa69c27e9ba8cd76922632e69d", "previous_migrations": ["20261030_163225_baseline"], "rollback_safe": true}]}
```

ساختار ردیف پیش از نوشتن با همان اعتبارسنجی گارد (`approval`) در محیط توسعه آزموده شد: مجموعهٔ کلیدهای دقیق، `rollback_safe` برابر `true`، هش ۶۴ کاراکتری hex و فهرست نام مهاجرت‌ها یکتا.

## پشتیبان

سیاست پشتیبان روی این میزبان `manual-local` است: `config/backup.json` فقط شامل `approved`، `transport`، `environment`، `no_real_customer_data` و `age_recipient` است و `secrets/backup-identity` موجود است؛ `config/backup-known-hosts` و `secrets/backup-ssh-key` وجود ندارند، چون انتقال SFTP پیکربندی نشده است. این حالت در گارد صریحاً برای پیش‌نمایش بدون دادهٔ واقعی مشتری مجاز است و رکورد پشتیبان را با `remote_path = manual-offsite-pending` می‌سازد.

نسخهٔ باقی‌ماندهٔ پشتیبان run ۱۹۸ که رکورد متناظر نداشت، حذف نشد و به `work/retained/backup-198-20261110160829.age` (۷۱۸۹۶ بایت، root، `0600`) منتقل شد تا `verify_backup` آن را به‌عنوان پشتیبان نامزد اشتباه نگیرد. فاز `backup-verify` پیش از هر تغییری اجرا شد و استقرار فقط پس از موفقیت آن ادامه یافت.

## مسیر اجرا

روی این میزبان کاربر `preview-deploy` وجود ندارد و `preview-deploy-client.py` هم نصب نیست؛ تنها کلید SSH موجود (`xennic-vps-vault-readonly`) برای Vault است. بنابراین استقرار از طریق همان برنامهٔ ممتاز ثابت و نصب‌شده انجام شد:

```
sudo sh -c 'python3 /usr/local/libexec/xennic-preview/preview-deploy-backend.py < /root/preview-request'
```

`preview-deploy-backend.py` فقط با root و بدون آرگومان اجرا می‌شود و ورودی را به شکل دقیق دو خطی (manifest، سپس توکن GitHub، سپس EOF) می‌خواند؛ همان ورودی‌ای که لایهٔ انتقال SSH نیز منتقل می‌کند. تمام بررسی‌های گارد داخل همین برنامه اجرا شدند: `readiness.check`، `verify_helpers`، `release-check` (شامل `approval`)، `pull-image`، `backup-verify`، `current-check`، `migrate` (تطبیق نام‌های ledger و هش درخت مهاجرت)، `activate` و `health`. هیچ بررسی‌ای حذف یا دور زده نشد؛ تنها لایهٔ انتقال SSH که روی این میزبان پیکربندی نشده بود حذف شد.

پیش از اجرای کامل، همان فاز فقط‌خواندنی `release-check` جداگانه اجرا شد و خروجی آن دقیقاً این بود:

```json
{"initial":false,"rollback_safe":true,"verified_commit":"a3a2316ce6031c2ad6fb71b6231174b0ce4d4e30","verified_digest":"sha256:4474049f29ef180704f2251353f2fe18abe743f735875bd30cf81ef2b6e9d57a","verified_run_number":207}
```

### هم‌ترازی helperها

مجموعهٔ نصب‌شده در `/usr/local/libexec/xennic-preview/` با نسخهٔ `a3a2316` می‌خواند، نه نسخهٔ قدیمی: اندازهٔ `release-check`/`activate`/`migrate`/`health`/`current-check`/`rollback` برابر ۴۶۵۸۷ بایت است، در حالی که همان فایل در `da6487b` برابر ۴۶۵۷۸ بایت بود (اختلاف ۹ بایتی همان افزودن `read:org` به scope پرووایدر GitHub). `preview-backup-operation.py` (۱۶۷۶۴)، `preview-deploy-backend.py` (۱۲۵۱۵) و `preview-deploy-readiness.py` (۷۷۸۹) هم مو‌به‌مو با `a3a2316` برابرند. بیست‌ویک فایل لازم (هشت فاز، `sftp-transfer`، `deploy-receiver` و یازده ماژول) همه با مالکیت root و بدون بیت گروه/دیگر نصب‌اند.

## نتیجهٔ اجرا

خروجی استقرار: `Preview deployment completed; verify release status.` با کد خروج صفر.

وضعیت ثبت‌شده در `/srv/xennic-preview/state/release-state.json`:

```json
{"blocked":false,"current":{"commit":"a3a2316ce6031c2ad6fb71b6231174b0ce4d4e30","digest":"sha256:4474049f29ef180704f2251353f2fe18abe743f735875bd30cf81ef2b6e9d57a","platform":"linux/amd64","repository":"feerozmandi/xennic-website","run_number":207},"last_run":207,"pending":null,"previous":[{"commit":"da6487b626c163092e33fd576f04594fb6fe7f97","digest":"sha256:d97511e3d0d288ab723d818c2b182c9212e874425e1d9c728a00551ada645109","platform":"linux/amd64","repository":"feerozmandi/xennic-website","run_number":198}],"version":1}
```

شاهد انتشار طراحی تازه روی دامنهٔ اصلی: `curl -s https://xennic.ir/ | grep -c -e hero__facts -e "دسترسی سریع"` مقدار `1` داد. پیش از استقرار همین شاهد صفر بود. نشانگر `hero__facts` و عنوان «دسترسی سریع» تنها در طراحی تازه وجود دارند؛ عبارت «چرا Xennic» نشانگر نسخه نیست، چون در هر دو طراحی هست.

## ریسک‌ها و کارهای باز

| مورد | وضعیت |
|---|---|
| انتقال پشتیبان به خارج VPS | **دستی و انجام‌نشده.** طبق سیاست `manual-local`، `work/backup.age` باید دستی از میزبان خارج شود؛ در غیر این صورت پشتیبان فقط روی همان دیسکی است که باید از آن محافظت کند. برای production، مقصد خودکار خارج از میزبان لازم است. |
| لایهٔ انتقال SSH استقرار | **پیکربندی‌نشده روی این میزبان.** استقرار با همان backend ثابت و به‌صورت root روی خود میزبان اجرا می‌شود؛ اگر مسیر SSH می‌خواهید، ساخت کاربر و کلید اختصاصی کار مستقل و حساس امنیتی است. |
| توکن دسترسی | `/root/.xennic-release-token` معتبر و با `actions: read` است، اما بلندمدت است. توکن کوتاه‌عمر (همان الگوی workflow) ترجیح دارد. |
| فایل درخواست موقت | `/root/preview-request` توکن را در خود دارد و باید پس از استقرار حذف شود. |
| داده و DNS | تغییری انجام نشد. هیچ مهاجرت جدیدی اجرا نشد (ledger بدون تغییر ماند). |

## پس از این

مرحلهٔ ۱ همین‌جا به پذیرش بصری مالک می‌رسد. پس از پذیرش، مرحلهٔ ۲ (دربارهٔ ما، خدمات، پیشینه) با همان سیستم طراحی و همان محدودیت‌های محتوایی ادامه می‌یابد؛ اطلاعات تماس مفقود همان فهرست کوتاه گزارش بازطراحی است و هیچ مقدار فرضی اضافه نمی‌شود.
