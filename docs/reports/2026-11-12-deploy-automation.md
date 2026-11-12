# استقرار خودکار `dev` روی VPS: چیزی که ساخته شد و کارهایی که فقط مالک می‌تواند انجام دهد

- **تاریخ:** ۲۰۲۶-۱۱-۱۲
- **شاخه:** `arena/79ed40e5-xennic-website` (بر پایهٔ `dev` = `42950e6`)
- **وضعیت:** کد و مستندات آماده است؛ **هیچ چیز روی سرور تغییر نکرده و هیچ استقراری خودکار نشده تا مالک مراحل بخش ۵ را انجام دهد.**
- **تصمیم مالک:** گزینهٔ **A** (GitHub Actions با تأیید یک‌کلیکی) و اطلاع‌رسانی خطا از طریق **GitHub Issue**.

## ۱) طرح در یک نگاه

```
push به dev
   └─ CI موجود: checks, compose-smoke, production-preview, installed-sftp, installer-upgrade
        └─ publish-preview-image   (ایمیج sha-<commit> منتشر و با همان digest آزموده می‌شود)
             └─ deploy-preflight   (فقط‌خواندنی) ← بدون تأیید، بدون تغییر
                  └─ deploy-dev    (environment: production-deploy ⇒ تأیید انسانی)
                       ├─ release-check  (فاز فقط‌خواندنی همان تراکنش گارددار)
                       ├─ deploy         (همان preview-deploy-backend.py بدون هیچ تغییری)
                       └─ بررسی /, /en, /services, /contact, /health
```

اگر ردیف گذار مهاجرت تأیید نشده باشد، `release-check` رد می‌شود و **هیچ تغییری روی سرور رخ نمی‌دهد**؛ همان لحظه یک Issue با علت باز می‌شود. تأیید ردیف، workflow جداگانه و گارددار خودش را دارد (بخش ۴).

**کلید ایمنی:** تا وقتی متغیر مخزن `DEPLOY_AUTOMATION` روی `enabled` نباشد، هر دو job جدید `skipped` می‌شوند. یعنی merge این تغییر به‌تنهایی هیچ رفتاری را عوض نمی‌کند.

## ۲) چه فایل‌هایی اضافه شد

| فایل | نقش |
| --- | --- |
| `scripts/preview-ci-gateway.py` | تنها برنامه‌ای که کلید CI اجازهٔ اجرایش را دارد؛ چهار دستور: `preflight`، `release-check`، `deploy`، `approve`. ریشه‌ای، بدون آرگومان آزاد، با اعتبارسنجی مانیفست از همان ماژول نصب‌شده |
| `scripts/preview-ci-gateway-ssh` | پوستهٔ forced-command؛ `SSH_ORIGINAL_COMMAND` را به argv امن تبدیل می‌کند (هیچ رشته‌ای با shell اجرا نمی‌شود) |
| `scripts/install-preview-ci-gateway.py` | نصب ریشه‌ای هر دو فایل با `0755`، بررسی مالکیت/حالت فایل‌های کمکی موجود، و چاپ SHA-256 نصب‌شده برای ثبت در گزارش انتشار |
| `scripts/preview-ci-evidence.py` | اتصال artifact انتشار به همان run: run_id، commit، run_number و digest باید بخوانند، وگرنه استقرار شروع نمی‌شود |
| `tests/preview-ci-gateway.py` | ۱۲ آزمون: allowlist دستورها، اعتبارسنجی ردیف گذار، رد ردیف تکراری/هدف تکراری، شکل مانیفست (در `npm run test:*`/CI اجرا می‌شود) |
| `tests/preview-ci-evidence.py` | ۴ آزمون: پذیرش فقط evidence همان run/commit، رد نسخه/شکل اشتباه، خروجی تک‌خطی CLI |
| `.github/workflows/ci.yml` | دو job تازه: `deploy-preflight` و `deploy-dev` (دومی با environment و Issue خودکار) |
| `.github/workflows/approve-release.yml` | تأیید یک ردیف گذار؛ دو مرحله‌ای: مرحلهٔ اول هش تصویر را می‌گوید، مرحلهٔ دوم همان هش را برمی‌گرداند |

### چرا `approve` دور زدن گارد نیست

1. run باید در environment `production-deploy` تأیید شود (فرد بازبین = مالک).
2. رهایی که تأیید می‌شود از artifact همان run خوانده و با GitHub API تطبیق داده می‌شود (`dev`، `success`، همان commit و run_number).
3. `ci-gateway approve` خودش `migration_tree_hash` را **از ایمیج pull‌شده** حساب می‌کند و اگر با هش ورودی برابر نباشد رد می‌کند (`migration hash mismatch: image gives …`).
4. `previous_migrations` را با جدول `website.payload_migrations` پایگاه‌دادهٔ **در حال اجرا** مقایسه می‌کند و در ناسازگاری رد می‌کند.
5. ردیف تکراری یا ردیف دوم به همان commit را رد می‌کند، فایل فعلی را در `/root/compatible-transitions.before-<run>.json` (‏`0600`، root) پشتیبان می‌گیرد و جای‌گذاری را اتمیک انجام می‌دهد.
6. فقط ردیف می‌نویسد؛ استقرار همچنان با فراخوانی جداگانهٔ `deploy` و همان فازهای گارددار انجام می‌شود.

## ۳) اطلاع‌رسانی خطا

| موقعیت | چه اتفاقی می‌افتد |
| --- | --- |
| CI شکست بخورد | ایمیل GitHub به مالک؛ job استقرار حتی اجرا نمی‌شود |
| `preflight` رد شود | job شکست می‌خورد و Summary می‌گوید کدام مرحله مانع است |
| `release-check` رد شود (گذار تأییدنشده) | Issue با برچسب `deploy-blocked` و دستور آمادهٔ approve؛ سرور دست‌نخورده |
| استقرار در هر فاز شکست بخورد | Issue با برچسب `deploy-failed`، لینک run و یادآوری `release-state.json` |
| approve رد شود | Issue با برچسب `deploy-blocked` و علت دقیق (هش، ledger، ردیف تکراری، فایل ناامن) |
| استقرار موفق | Issue باز همان commit بسته می‌شود؛ Summary شامل کد پنج مسیر |

برچسب‌های `deploy-failed` و `deploy-blocked` باید یک‌بار در مخزن ساخته شوند (بخش ۵).

## ۴) کارهایی که فقط مالک می‌تواند انجام دهد

### ۴٫۱ روی VPS (یک‌بار، با `sudo -i`)

```bash
# 1) کاربر deploy بدون شل تعاملی و بدون رمز
useradd --create-home --shell /bin/bash --comment "xennic CI deploy" deploy
passwd -l deploy

# 2) نصب gateway از همان commit ادغام‌شده (نه از نسخهٔ محلی)
C=$(git --git-dir=/srv/xennic-preview/.git rev-parse HEAD 2>/dev/null || echo MERGED_COMMIT)
mkdir -p /root/xennic-preview-ci-gateway
curl -fsSL "https://raw.githubusercontent.com/feerozmandi/xennic-website/$C/scripts/preview-ci-gateway.py" -o /root/xennic-preview-ci-gateway/preview-ci-gateway.py
curl -fsSL "https://raw.githubusercontent.com/feerozmandi/xennic-website/$C/scripts/preview-ci-gateway-ssh" -o /root/xennic-preview-ci-gateway/preview-ci-gateway-ssh
curl -fsSL "https://raw.githubusercontent.com/feerozmandi/xennic-website/$C/scripts/install-preview-ci-gateway.py" -o /root/xennic-preview-ci-gateway/install-preview-ci-gateway.py
chmod 700 /root/xennic-preview-ci-gateway
python3 /root/xennic-preview-ci-gateway/install-preview-ci-gateway.py

# 3) sudo فقط برای همان یک فایل، با حفظ SSH_ORIGINAL_COMMAND
printf 'Defaults:deploy env_keep += "SSH_ORIGINAL_COMMAND"\ndeploy ALL=(root) NOPASSWD: /usr/local/libexec/xennic-preview/ci-gateway-ssh\n' > /etc/sudoers.d/xennic-ci-gateway
chmod 0440 /etc/sudoers.d/xennic-ci-gateway
visudo -c
```

`MERGED_COMMIT` همان SHA مرج این PR است؛ اگر `git` در `/srv/xennic-preview` نیست، مقدار را دستی بگذارید. مقدار چاپ‌شدهٔ SHA-256 نصب را برای گزارش انتشار نگه دارید.

### ۴٫۲ روی رایانهٔ خودتان (ساخت کلید)

```bash
ssh-keygen -t ed25519 -C "ci-deploy@github" -f ~/.ssh/xennic-ci-deploy -N ''
cat ~/.ssh/xennic-ci-deploy.pub          # این خط در authorized_keys می‌رود
ssh-keyscan -p 33878 185.192.113.199 > ~/.ssh/xennic-ci-known-hosts
```

### ۴٫۳ روی VPS (نصب کلید)

```bash
install -d -m 0700 -o deploy -g deploy /home/deploy/.ssh
printf '%s\n' 'restrict,command="sudo -n /usr/local/libexec/xennic-preview/ci-gateway-ssh" ssh-ed25519 AAAA… ci-deploy@github' > /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 0600 /home/deploy/.ssh/authorized_keys
# آزمون: باید JSON پیش‌پرواز برگردد و هیچ دستور دیگری کار نکند
ssh -i ~/.ssh/xennic-ci-deploy -p 33878 deploy@185.192.113.199 preflight < /dev/null
```

`preflight` به ورودی مانیفست نیاز دارد؛ آزمون واقعی پس از فعال‌سازی workflow انجام می‌شود. برای آزمون دستی، خط مانیفست آخرین انتشار را از `release-state.json` بسازید:

```bash
python3 -c 'import json;d=json.load(open("/srv/xennic-preview/state/release-state.json"))["current"];print(json.dumps(d,sort_keys=True,separators=(",",":")),end="\n")' > /tmp/m.json
sudo -u deploy ssh -i /root/.ssh/… deploy@127.0.0.1 preflight < /tmp/m.json   # فقط نمونهٔ محلی
```

### ۴٫۴ در GitHub (Settings)

| نوع | نام | مقدار |
| --- | --- | --- |
| Variable | `VPS_HOST` | `185.192.113.199` |
| Variable | `VPS_PORT` | `33878` |
| Variable | `DEPLOY_AUTOMATION` | **`disabled`** تا زمان آزمون؛ سپس `enabled` |
| Secret | `VPS_DEPLOY_KEY` | محتوای `~/.ssh/xennic-ci-deploy` (کلید خصوصی) |
| Secret | `VPS_KNOWN_HOSTS` | محتوای `~/.ssh/xennic-ci-known-hosts` |
| Environment | `production-deploy` | Required reviewers = مالک؛ Deployment branches = `dev` |
| Label | `deploy-failed`، `deploy-blocked` | رنگ دلخواه، بدون توضیح لازم |

`gh` معادل:

```bash
gh variable set VPS_HOST --body 185.192.113.199 --repo feerozmandi/xennic-website
gh variable set VPS_PORT --body 33878 --repo feerozmandi/xennic-website
gh variable set DEPLOY_AUTOMATION --body disabled --repo feerozmandi/xennic-website
gh secret set VPS_DEPLOY_KEY < ~/.ssh/xennic-ci-deploy --repo feerozmandi/xennic-website
gh secret set VPS_KNOWN_HOSTS < ~/.ssh/xennic-ci-known-hosts --repo feerozmandi/xennic-website
gh label create deploy-failed --color B60205 --repo feerozmandi/xennic-website
gh label create deploy-blocked --color D93F0B --repo feerozmandi/xennic-website
```

Environment و بازبین را فقط از رابط وب می‌توان تنظیم کرد: Settings → Environments → New environment → `production-deploy` → Required reviewers → خودتان → Save.

## ۵) اولین اجرا (آزمون کنترل‌شده)

1. `DEPLOY_AUTOMATION` روی `enabled` بگذارید.
2. یک merge کوچک به `dev` انجام دهید (یا همان commit جاری را با `gh workflow run` دوباره اجرا کنید). `deploy-preflight` باید بدون هیچ تأییدی اجرا شود و در Summary بگوید:
   - کدام run زنده است،
   - آیا ردیف گذار برای این commit وجود دارد.
3. اگر ردیف نیست: `deploy-dev` منتظر تأیید می‌ماند و پس از تأیید در `release-check` با Issue متوقف می‌شود — این رفتار درست است.
4. تأیید ردیف:
   ```bash
   gh workflow run approve-release.yml --repo feerozmandi/xennic-website \
     -f run_id=<run id> -f previous_migrations='["20261030_163225_baseline"]' -f migration_sha256=0000…0000
   ```
   Output همان run هش واقعی تصویر را چاپ می‌کند و رد می‌شود (هیچ چیزی نوشته نمی‌شود).
5. همان دستور را با هش چاپ‌شده تکرار کنید. این بار ردیف نوشته و پشتیبان گرفته می‌شود.
6. `deploy-dev` را از Actions دوباره اجرا/تأیید کنید؛ استقرار کامل انجام و پنج مسیر بررسی می‌شود.

## ۶) خاموش‌کردن یا عقب‌نشینی

- توقف فوری: `gh variable set DEPLOY_AUTOMATION --body disabled` (هر دو job `skipped` می‌شوند).
- حذف کامل: حذف `/etc/sudoers.d/xennic-ci-gateway`، حذف کلید از `authorized_keys`، حذف Secrets/Variables و بازگرداندن `ci.yml` به نسخهٔ قبل. هیچ‌کدام به مسیر تولید دست نمی‌زند.
- ردیف اشتباه در فایل گذار: از پشتیبان `/root/compatible-transitions.before-<run>.json` بازگردانید (فایل با `0600` و root).

## ۷) آزمون‌های انجام‌شده در این تغییر

| آزمون | نتیجه |
| --- | --- |
| `python3 tests/preview-ci-gateway.py` | ۱۲/۱۲ |
| `python3 tests/preview-ci-evidence.py` | ۴/۴ |
| `bash -n scripts/preview-ci-gateway-ssh` | پاک |
| اعتبارسنجی YAML هر دو workflow | پاک؛ jobها: `deploy-preflight`، `deploy-dev`، `approve` |
| `npm run verify` / `npm run build` / `npm run test:smoke` | سبز (هیچ فایل برنامه‌ای تغییر نکرد) |

آنچه **آزمون نشده و نمی‌تواند در CI آزموده شود**: خود SSH، نصب sudoers و اجرای docker روی میزبان. این‌ها همان مراحل بخش ۴ هستند و اولین اجرای بخش ۵ جای آزمون واقعی است.

## ریسک‌ها

- **کلید CI روی میزبان تولید:** فقط یک فرمان ثابت را اجرا می‌کند، ولی اگر افشا شود مهاجرت/استقرار ممکن است؛ چرخش کلید یک دستور است (`ssh-keygen` تازه + جای‌گذاری در `authorized_keys` و Secret).
- **وضعیت میانی ناموفق:** همان رفتار تراکنش فعلی؛ `release-state.json` و backup معتبر مرجع‌اند. Issue خودکار می‌گوید کدام فاز متوقف شده.
- **هم‌زمانی:** `concurrency: deploy-dev` جلوی دو استقرار هم‌زمان را می‌گیرد؛ approve هم با همان گروه قفل می‌شود.
- **توکن بلندمدت `/root/.xennic-release-token`:** همچنان لازم است (برای `release-check`/`deploy`)؛ توکن کوتاه‌عمر کار جداگانه‌ای است.

## پیگیری Vault

نیازی شناسایی نشد؛ هیچ ادعا، شماره یا محتوای تازه‌ای منتشر نشد. این گزارش ثبت در Vault محسوب نمی‌شود.
