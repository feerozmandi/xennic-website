# گزارش: گذار محدود لبه به دامنهٔ اصلی و روشن‌کردن سایت

- **تاریخ گزارش:** ۲۰۲۶-۱۰-۲۹؛ تاریخ محیط GitHub تأیید نشده است.
- **مبنا:** [PR #26](https://github.com/feerozmandi/xennic-website/pull/26)، پایهٔ dev `00d78f4f9a08dbcfa5703937c8752ccfb9fec82f`.
- **وضعیت:** گذار آماده و آزمون محلی شده؛ **روی VPS اجرا یا نصب نشده است.**

## چه چیزی اضافه شد

- `config/apex-gateway-compose.yml`: همان Compose لبه با `PUBLIC_AUTHORITY: xennic.ir`؛ تنها تفاوت همین یک خط است.
- `scripts/preview-fixed-operations.py`: مرجع لبه فقط از هش Caddyfile نصب‌شده استخراج می‌شود (`edge_authority`). هیچ env، request یا argv نمی‌تواند حالت را انتخاب کند. فایل ناشناخته یا symlink به شکست بسته می‌رسد. probe اکنون برای هر دو حالت apex و preview فهرست ثابت دارد؛ در حالت apex صفحهٔ عمومی باید HTML موفق و admin/API/GraphQL/media، POST و hostهای دیگر باید بسته باشند.
- `scripts/install-preview-sftp-helper.py`: مسیرهای `--upgrade-apex` و `--rollback-apex`. گذار فقط در وضعیت pre-first-deployment (بدون journal، state و work خالی) اجرا می‌شود، فایل‌های edge، سیاست OAuth و origin staging را با هم و اتمی عوض می‌کند، نسخه‌های قبلی helper و فایل‌های اصلی را نگه می‌دارد و در هر خطا همه را برمی‌گرداند. سیاست OAuth با بازنویسی قطعی ساخته و با validator همان helper به‌صورت apex اعتبارسنجی می‌شود؛ secret چاپ نمی‌شود.
- `scripts/preview-deploy-readiness.py`: استثنای backup دستی فقط دو origin بازبینی‌شده (`preview.xennic.ir` و `xennic.ir`) را می‌پذیرد؛ attestation «بدون دادهٔ مشتری واقعی» همچنان الزامی است.

## آزمون‌ها

| آزمون | محیط | نتیجه |
|---|---|---|
| `tests/preview-installer-apex.py` | محلی | ۷ تست موفق: سیاست OAuth apex/preview، جایگزینی خط‌دقیق origin و هش فایل‌های بازبینی‌شده |
| `tests/preview-network-topology.py` | محلی | ۱۸ تست موفق: استخراج authority از فایل، رد فایل ناشناخته/لینک و probe fail-closed |
| `tests/preview-deploy-readiness.py` | محلی | ۸ تست موفق |
| CI کامل شاخه | GitHub Actions | در انتظار نتیجه |

این آزمون‌ها گذار روی VPS، ACME عمومی، ورود OAuth واقعی و اولین migration/seed را ثابت نمی‌کنند.

## روشن‌کردن سایت: گام‌های باقی‌مانده

1. **پیش‌نیاز مالک (خارج از repo):** در تنظیمات GitHub OAuth App، callback را به `https://xennic.ir/oauth2/callback` تغییر دهید؛ بدون آن ورود مدیریت کار نمی‌کند.
2. پس از انتشار artifact همین شاخه و تأیید digest، آرشیو منتشرشده در `/root/xennic-preview-install/incoming-apex` مستقر شود (بدون کپی دستی فایل تکی).
3. `sudo python3 /root/xennic-preview-install/install-preview-sftp-helper.py --upgrade-apex` و سپس بررسی این‌که guard همان apex را می‌بیند.
4. اولین استقرار برنامه: migration و seed مصوب و سپس start با همان زنجیرهٔ محدود؛ این گام به توکن موقت Actions read برای verifier یا تأیید صریح یک bootstrap محدود نیاز دارد. توکن نباید در گفتگو یا argv باشد.
5. بررسی واقعی: HTTPS عمومی صفحه، ورود OAuth، حفاظت admin/API، قطع gate و rollback.

در شکست، `--rollback-apex` همه‌چیز را به لبهٔ preview بازمی‌گرداند؛ اگر نشانهٔ فایل نیمه‌نوشته دیده شد، اجرای مجدد نکنید و ابتدا وضعیت را بررسی کنید.

## ریسک‌ها

- محدودهٔ Vault §۱۰ هنوز preview خصوصی است؛ عمومی‌شدن apex نیازمند هم‌راستاسازی مدیریت است و این گزارش مجوز استقرار نیست.
- پشتیبانی که backup می‌گیرد شاهد offsite/restore ندارد؛ پیش از داده واقعی، backup عملیاتی لازم است.

## پیگیری Vault

پیگیری مستقل `META-INT-140` §۱۰ برای محدودهٔ عمومی لازم است؛ Vault در این نشست فقط‌خواندنی بوده است.
