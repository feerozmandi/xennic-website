# استقرار کششی: میزبان از گیت‌هاب می‌پرسد، گیت‌هاب به میزبان وصل نمی‌شود

- **تاریخ:** ۲۰۲۶-۱۱-۱۲
- **شاخه:** `arena/01ef5de9-xennic-website` (بر پایهٔ `dev` = `95fe6b8`)
- **تصمیم مالک:** استقرار خودکار به روش **کششی** (pull) ادامه یابد؛ انتشار دستی فعلی هم انجام شود.
- **وضعیت:** کد و مستندات آماده است؛ **نصب روی سرور انجام نشده** و تا اجرای دستورهای بخش ۵ هیچ timerی فعال نیست.

## ۱) چرا مدل عوض شد

مسیر push با GitHub Actions آزموده شد و نتیجه قطعی است:

| اندازه‌گیری | مقدار |
| --- | --- |
| آدرس خروجی runner | `20.29.191.7` |
| اتصال runner به `185.192.113.199:33878` | timeout ۱۵ ثانیه |
| اتصال runner به همان میزبان روی پورت ۲۲ | timeout ۱۵ ثانیه |
| اتصال از رایانهٔ مالک به `:33878` | موفق در میلی‌ثانیه |

یعنی **کل آدرس مبدأ** برای این میزبان بسته است، نه یک پورت؛ افزودن ~۱۲۰ قاعدهٔ `ufw` برای محدوده‌های GitHub Actions هم چیزی را عوض نکرد، پس لایهٔ حاکم جای دیگری است (فایروال پنل/Plesk، `ipset`، `fail2ban` یا upstream). به‌جای جنگیدن با آن لایه، جهت اتصال برعکس شد: **میزبان خودش با HTTPS از گیت‌هاب می‌پرسد**. هیچ درگاه ورودی لازم نیست و سطح حمله هم کم می‌شود.

## ۲) زنجیرهٔ کششی

```
xennic-pull-deploy.timer  (هر ۵ دقیقه، systemd، root)
   └─ ci-pull-deploy
        ├─ ۱. قفل مشترک استقرار (نبودِ قفل ⇒ کسی دیگری در حال استقرار است ⇒ خروج بی‌صدا)
        ├─ ۲. GitHub: آخرین run موفق push روی dev، و همان commit باید head فعلی dev باشد
        ├─ ۳. artifact همان run دانلود و با preview-ci-evidence.py به run_id/commit/run_number قفل می‌شود
        ├─ ۴. مقایسه با ژورنال release-state.json
        │      همان نسخه؟ ⇒ خروج بی‌صدا
        │      pending دارد؟ ⇒ in-flight ⇒ خروج
        ├─ ۵. ردیف گذار reviewed برای همین جفت commit وجود دارد؟
        │      نه  ⇒ ثبت waiting-approval + یک اعلان + خروج (**هیچ تغییری روی سایت**)
        │      بله ⇒ ادامه
        ├─ ۶. همان preview-deploy-backend.py با همان پروتکل دو خطی (مانیفست + توکن)
        └─ ۷. بررسی عمومی https://xennic.ir/health و اعلان نتیجه
```

سه قید مهم:

1. **گارد دست‌نخورده است.** خودِ backend دوباره `release-check` و تطبیق ردیف گذار و هش درخت مهاجرت را انجام می‌دهد؛ این برنامه فقط «کی در بزند» را تعیین می‌کند.
2. **تأیید انسانی باقی است.** بدون ردیف `from_commit → to_commit` در `compatible-transitions.json`، هیچ استقراری رخ نمی‌دهد؛ فقط یک اعلان می‌آید.
3. **توکن گیت‌هاب فقط خواندنی است.** همان `/root/.xennic-release-token` با `actions: read`؛ برنامه‌نویس حق نوشتن روی مخزن ندارد.

## ۳) آنچه اضافه شد

| فایل | نقش |
| --- | --- |
| `scripts/preview-pull-deploy.py` | برنامهٔ اصلی؛ نصب‌شده به‌نام `ci-pull-deploy` در `/usr/local/libexec/xennic-preview/` با مالک root و `0755` |
| `scripts/install-preview-pull-deploy.py` | نصب اتمیک برنامه + `xennic-pull-deploy.service` و `.timer`، `daemon-reload` و فعال‌سازی timer، چاپ SHA-256 نصب‌شده |
| `tests/preview-pull-deploy.py` | ۱۵ آزمون: تصمیم‌گیری، اعتبارسنجی ردیف گذار، رکورد `0600`، اعلان بی‌خطر، انتخاب درست run |
| `.github/workflows/ci.yml` | اجرای تست تازه در job `checks`؛ مسیر push حالا با متغیر جدا `DEPLOY_PUSH_SSH` کنترل می‌شود تا هر merge با خطای شبکه آلوده نشود |

## ۴) اعلان خطا — ربات بله

اعلان از **بله** (پیام‌رسان رسمی سازمان) ارسال می‌شود؛ API بازوی بله با تلگرام سازگار است و آدرس پایهٔ آن `https://tapi.bale.ai/bot<token>/sendMessage` است. تلگرام هم همچنان به‌عنوان گزینهٔ دوم پشتیبانی می‌شود (`"provider": "telegram"`)، ولی پیش‌فرض بله است.

### ساختن فایل تنظیمات از همان `.env` زیرساخت

اطلاعات ربات از قبل در یک جا روی میزبان است (`/home/xennic/xennic-infra/.env` با کلیدهای `BALE_NAME_BOT`، `BALE_TOKEN_BOT`، `BALE_CHAT_ID`). اسکریپت `scripts/configure-preview-notify.py` همان را می‌خواند و فایل نهایی را می‌سازد، بدون اینکه توکن را چاپ کند:

```
sudo -i; python3 /root/xennic-preview-pull-deploy/configure-preview-notify.py --send-test; echo "exit=$?"
```

- خروجی فقط `provider`، `chat_id` و **طول** توکن را نشان می‌دهد، نه خود توکن.
- فایل مبدأ باید root-owned و `0600` باشد؛ `.env` با حالت `0644` رد می‌شود (این همان خطری است که اسکریپت می‌خواهد نباشد).
- `--send-test` پس از نوشتن، یک پیام آزمایشی می‌فرستد و فقط `ok:true` را قبول می‌کند.
- مسیر دیگر با `--source /path/.env` قابل تغییر است.

### فایل تنظیمات (روی میزبان، مالک root، `0600`)

`/srv/xennic-preview/secrets/notify.json`:

```json
{"provider": "bale", "bot_token": "123456789:AAH…", "chat_id": "-1001234567890"}
```

- `provider` اختیاری است؛ نبودش یعنی `bale`.
- `chat_id` می‌تواند شناسهٔ عددی (کاربر، گروه یا کانال) یا نام کاربری کانال با فرمت `@channel` باشد.
- کلیدهای قدیمی `telegram_bot_token` و `telegram_chat_id` هم خوانده می‌شوند تا فایل موجود پس از ارتقا نشکند.

### گرفتن توکن و شناسهٔ چت

1. در بله به **@BotFather** پیام دهید → `/newbot` → نام و نام‌کاربری (مثلاً `xennic_deploy_bot`) → توکن `HTTP API` را بگیرید.
2. ربات را در گروه/کانال موردنظر اضافه کنید (یا خودتان به آن پیام دهید).
3. شناسهٔ چت را از `getUpdates` بخوانید:

```
curl -s "https://tapi.bale.ai/bot<TOKEN>/getUpdates" | python3 -c 'import json,sys; d=json.load(sys.stdin); print([r.get("message",{}).get("chat",{}) for r in d.get("result",[])])'
```

4. آزمون ارسال:

```
curl -s -X POST "https://tapi.bale.ai/bot<TOKEN>/sendMessage" -H 'Content-Type: application/json' -d '{"chat_id":"<CHAT>","text":"Xennic deploy notifications are connected."}'; echo "exit=$?"
```

### قواعد ایمنی که در کد رعایت شده

| موضوع | رفتار |
| --- | --- |
| توکن در مسیر URL است | فقط دو میزبان دقیق مجازند (`tapi.bale.ai` و `api.telegram.org`)، بقیه در `notification_target` رد می‌شوند |
| ریدایرکت | دنبال نمی‌شود (`NoRedirect`)، تا توکن به میزبان دیگری نرسد |
| فایل تنظیمات | فقط root-owned با حالت `0600` خوانده می‌شود؛ در غیر این صورت اعلان خاموش می‌ماند |
| خطای ارسال | هرگز استقرار را متوقف نمی‌کند؛ نتیجه در `state/pull-deploy.json` می‌ماند |
| تکرار | پیام «منتظر تأیید» برای هر run فقط یک بار فرستاده می‌شود |

## ۵) نصب (یک‌بار، با `sudo -i`)

```
C=38ad1707c176ab62ed084d4335dd2fc72e4b6e75; echo "exit=$?"
mkdir -p /root/xennic-preview-pull-deploy; chmod 700 /root/xennic-preview-pull-deploy; echo "exit=$?"
curl -fsSL "https://raw.githubusercontent.com/feerozmandi/xennic-website/$C/scripts/preview-pull-deploy.py" -o /root/xennic-preview-pull-deploy/preview-pull-deploy.py; echo "exit=$?"
curl -fsSL "https://raw.githubusercontent.com/feerozmandi/xennic-website/$C/scripts/preview-ci-evidence.py" -o /root/xennic-preview-pull-deploy/preview-ci-evidence.py; echo "exit=$?"
curl -fsSL "https://raw.githubusercontent.com/feerozmandi/xennic-website/$C/scripts/install-preview-pull-deploy.py" -o /root/xennic-preview-pull-deploy/install-preview-pull-deploy.py; echo "exit=$?"
python3 /root/xennic-preview-pull-deploy/install-preview-pull-deploy.py; echo "exit=$?"
/usr/local/libexec/xennic-preview/ci-pull-deploy --dry-run; echo "exit=$?"
journalctl -u xennic-pull-deploy.service -n 30 --no-pager; echo "exit=$?"
systemctl list-timers xennic-pull-deploy.timer --no-pager; echo "exit=$?"
```

**سه فایل لازم است، نه دو.** نخستین نسخهٔ این دستور فقط دو فایل را دانلود می‌کرد و پوشهٔ مبدأ هم ساخته نمی‌شد؛ نتیجه `curl: (23) Failure writing output to destination` بود.

پس از رفع آن، نصب در مرحلهٔ بررسی فایل‌های موجود شکست خورد:

```
pull deploy install failed: /usr/local/libexec/xennic-preview/preview-fixed-operations.py is missing
```

این درخواست از پایه غلط بود: نصب‌کنندهٔ helperها `preview-fixed-operations.py` را **هرگز با این نام** نصب نمی‌کند؛ نسخه‌هایی از آن را با نام فازها می‌نویسد (`release-check`، `migrate`، `activate`، `health`، `rollback`، `current-check`) و بک‌اند همان‌ها را اجرا می‌کند. فهرست `REQUIRED` اکنون فقط چیزهایی را می‌خواهد که واقعاً روی میزبان وجود دارند: ماژول‌های پایتون نصب‌شده به‌همراه `pull-image` و شش فاز بالا. همین اشتباه در `ci-gateway` هم بود و اصلاح شد (کپی نصب‌شدهٔ `release-check` بارگذاری می‌شود).

| فایل مبدأ | مقصد |
| --- | --- |
| `preview-pull-deploy.py` | `/usr/local/libexec/xennic-preview/ci-pull-deploy` (0755) |
| `preview-ci-evidence.py` | `/usr/local/libexec/xennic-preview/preview-ci-evidence.py` (0644) |
| `install-preview-pull-deploy.py` | فقط اجرا می‌شود |

سه آزمون تازه در `tests/preview-pull-deploy.py` جلوی تکرار این خطا را می‌گیرند: هر ماژولی که deployer در زمان اجرا بارگذاری می‌کند باید نصب شود، هیچ فایلی نباید خواسته شود که نصب helper آن را نمی‌سازد، و نام منبع `preview-fixed-operations.py` هرگز نباید در فهرست باشد.

## ۶) چرخهٔ روزمره پس از نصب

1. merge به `dev` → CI ایمیج را منتشر می‌کند.
2. تا ۵ دقیقه بعد، timer آن run را می‌بیند و پیام «منتظر تأیید» می‌فرستد.
3. مالک ردیف گذار را تأیید می‌کند (روش زیر).
4. tick بعدی استقرار را انجام می‌دهد، `/health` را می‌بیند و پیام «منتشر شد» می‌فرستد.

**تأیید ردیف** (از رایانهٔ خودتان، بدون تایپ هش):

```
./scripts/approve-transition.sh --run-id <run id> --migrations '["20261030_163225_baseline"]'; echo "exit=$?"
```

اگر آن run قبلاً در `pull-deploy.json` ثبت شده، `preflight` همان run را تأیید می‌کند و ردیف نوشته می‌شود.

## ۷) خاموش‌کردن

```
systemctl disable --now xennic-pull-deploy.timer; echo "exit=$?"
```

حذف کامل: همان دستور + `rm /etc/systemd/system/xennic-pull-deploy.*` + `systemctl daemon-reload` + `rm /usr/local/libexec/xennic-preview/ci-pull-deploy`. هیچ‌کدام به مسیر تولید دست نمی‌زند.

## ۸) ریسک‌ها

| ریسک | پاسخ |
| --- | --- |
| timer دو استقرار هم‌زمان بزند | قفل مشترک `/run/lock/xennic-preview-deploy.lock` با `nonblocking` و همان قفلِ مسیر دستی |
| GitHub در دسترس نباشد | خروج با کد ۱ و پیام کوتاه؛ هیچ تغییری روی سایت |
| artifact منقضی شود | حالت `waiting-approval` تکرار می‌شود و در لاگ می‌ماند؛ انتشار تازه با merge بعدی می‌آید |
| اعلان تلگرام قطع باشد | استقرار مستقل از اعلان انجام می‌شود؛ نتیجه در `pull-deploy.json` و journal می‌ماند |
| مسیر push دوباره فعال شود | فقط با `DEPLOY_PUSH_SSH=enabled`؛ پیش‌فرض خاموش است و شکست شبکه را تکرار نمی‌کند |

## ۹) تشخیص شبکه‌ای که ناتمام ماند

دستور جمع‌بندی روی میزبان (پیشنهاد برای وقتی دسترسی دارید):

```
{ ss -lntp | grep -E ':33878|:22'; ufw status verbose; iptables -S | head -30; ipset list -n; fail2ban-client status sshd; } 2>&1 | tee /tmp/net-diag.txt
```

اگر بعداً خواستید مسیر push هم برگردد، همین خروجی نشان می‌دهد باید در کدام لایه (Plesk firewall / iptables / ipset / provider) قاعده گذاشت. برای مدل کششی لازم نیست.

## پیگیری Vault

نیازی شناسایی نشد؛ هیچ ادعا، شماره یا محتوای تازه‌ای منتشر نشد و این گزارش ثبت در Vault محسوب نمی‌شود.
