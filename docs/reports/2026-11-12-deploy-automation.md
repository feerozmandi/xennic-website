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

## ۸) اجرای آزمایشی اول (همین ادغام)

این ادغام عمداً کوچک است و هیچ فایل برنامه‌ای را تغییر نمی‌دهد؛ تنها هدفش اجرای واقعی زنجیره است:

| گام | انتظار |
| --- | --- |
| `checks`، `compose-smoke`، `installed-sftp`، `installer-upgrade`، `production-preview` | سبز، مثل هر merge دیگر |
| `publish-preview-image` | ایمیج همان commit منتشر و با همان digest آزموده شود |
| `deploy-preflight` | بدون تأیید اجرا شود و در Summary بگوید کدام run زنده است |
| `deploy-dev` | اگر ردیف گذار این commit وجود نداشته باشد، `release-check` رد می‌کند، Issue با برچسب `deploy-blocked` باز می‌شود و **سایت دست‌نخورده می‌ماند** |

نتیجهٔ همین آزمون، سندِ رفتار گارد است: استقرار تنها وقتی انجام می‌شود که ردیف گذار تأییدشده باشد.

**یادآوری تنظیمات:** در مخزن، environment `production-deploy` ساخته شده ولی **هیچ بازبینی برایش ثبت نشده** است (`protection_rules` فقط `branch_policy` دارد و فهرست بازبین‌ها خالی است). یعنی `deploy-dev` پس از `preflight` بی‌درنگ اجرا می‌شود. برای فعال‌کردن همان «تأیید یک‌کلیکی» که توافق شد، در Settings → Environments → `production-deploy` → **Required reviewers** خودتان را اضافه کنید و لازم است گزینهٔ `Prevent self-review` خاموش بماند تا تأیید همان اجرا ممکن باشد.

## ۹) نتیجهٔ اولین ادغام آزمایشی (run ۲۳۷)

| مورد | نتیجه |
| --- | --- |
| `checks`، `compose-smoke`، `installed-sftp`، `installer-upgrade`، `production-preview` | سبز |
| `publish-preview-image` | موفق؛ ایمیج `c3818a3` منتشر و با همان digest آزموده شد |
| `deploy-preflight` | **skipped** |
| `deploy-dev` | **skipped** |
| سایت | دست‌نخورده (همان run ۲۳۶ روی `eb5b9b9`) |

علت: `vars.DEPLOY_AUTOMATION` تعریف نشده بود، پس شرط هر دو job `false` شد. این همان قفل ایمنی است که عمداً گذاشته شد — تا وقتی متغیر `enabled` نشود، هیچ تماسی با سرور برقرار نمی‌شود.

**برای آزمون واقعی بدون commit تازه:** پس از ساختن متغیرها، همین run را دوباره اجرا کنید؛ شرط‌ها هنگام اجرای مجدد از نو ارزیابی می‌شوند و زنجیره کامل می‌شود:

```
gh run rerun 43248281586 --repo feerozmandi/xennic-website; echo "exit=$?"
```

پس از آن، Summary مرحلهٔ `deploy-preflight` می‌گوید کدام run زنده است و آیا ردیف گذار برای `c3818a3` وجود دارد. چون migration_tree بین نسخه‌های اخیر تغییر نکرده (`9f66a5fa…`)، اگر ردیف `eb5b9b9 → c3818a3` را با همان هش تأیید نکنید، `release-check` رد می‌کند و Issue باز می‌شود — دقیقاً رفتار مورد انتظار.

## ۱۰) وضعیت شاخه‌ها پس از این نشست

- شاخه‌های ادغام‌شده (۳۶ شاخه) و شش شاخهٔ باقی‌ماندهٔ قدیمی با تأیید مالک حذف شدند؛ چهار PR باز (#12، #14، #18، #22) با توضیح دلیل بسته شدند، چون محتوایشان با verifier و CI فعلی جایگزین شده بود و هیچ‌کدام در `dev` نبود.
- اکنون فقط `dev` و `main` روی مخزن باقی مانده‌اند. شاخه‌های نشست‌های Arena پس از merge حذف می‌شوند؛ تاریخ کار در `docs/status.md` و همین گزارش‌ها می‌ماند، پس حذف شاخه هیچ سابقه‌ای را از بین نمی‌برد.

## ۱۱) اولین اجرای واقعی (run ۲۴۰، اجرای مجدد): دو مانع و رفعشان

پس از ساخت متغیرها، run ۲۴۰ دوباره اجرا شد. این بار `deploy-preflight` **واقعاً اجرا شد** و شکست خورد؛ `deploy-dev` به‌درستی اجرا نشد. دو مانع جدا بود:

### مانع ۱ — `gh workflow run approve-release.yml` پاسخ ۴۰۴ داد

GitHub فقط workflowهایی را با `workflow_dispatch` اجرا می‌کند که فایلشان روی **شاخهٔ پیش‌فرض (`main`)** باشد. `approve-release.yml` روی `dev` است و `main` هنوز آن را ندارد، بنابراین API مسیر را نمی‌شناسد.

**رفع فوری (بدون تغییر مخزن):** اسکریپت `scripts/approve-transition.sh` همان دو مرحله را از رایانهٔ خودتان روی همان forced-command انجام می‌دهد:

```
./scripts/approve-transition.sh --run-id 43257283235 --migrations '["20261030_163225_baseline"]'
```

اسکریپت: run را تأیید می‌کند (`dev` و `success`)، artifact همان run را می‌گیرد، مانیفست را با `preview-ci-evidence.py` قفل می‌کند، `preflight` می‌گیرد، سپس دو پاس approve را می‌زند و ردیف نهایی را چاپ می‌کند. هیچ هشی دستی تایپ نمی‌شود.

**رفع دائمی:** وقتی `dev` به `main` منتشر شد (یا اگر مالک بخواهد، با یک PR کوچک مخصوص `main` فقط برای همین فایل)، `workflow_dispatch` کار می‌کند و همان مسیر از رابط وب هم در دسترس است.

### مانع ۲ — مرحلهٔ `Read the live state` با کد ۲۵۵ و پس از ~۲ دقیقه شکست خورد

مدت اجرا (۱۷:۰۲:۳۴ تا ۱۷:۰۴:۴۷) و کد ۲۵۵ نشانهٔ **timeout در برقراری TCP** است، نه رد کلید (رد کلید فوری است). یعنی runner گیت‌هاب نتوانست پورت `33878` میزبان را باز کند.

اقدام لازم (به ترتیب):

1. صحت متغیرها: `VPS_HOST` = `185.192.113.199` و `VPS_PORT` = `33878`.
2. روی VPS بررسی کنید sshd روی همان پورت گوش می‌دهد و فایروال اجازه می‌دهد:
   ```
   ss -lntp | grep -E ':33878|:22'; echo "exit=$?"
   ufw status verbose; echo "exit=$?"
   iptables -S | head -40; echo "exit=$?"
   grep -E '^(Port|ListenAddress|AllowUsers)' /etc/ssh/sshd_config; echo "exit=$?"
   journalctl -u ssh --since '-30 min' | tail -20; echo "exit=$?"
   ```
3. از رایانهٔ خودتان همان مسیر را با GitHub مقایسه کنید:
   ```
   nc -vz -w 5 185.192.113.199 33878; echo "exit=$?"
   ```
   اگر از لپ‌تاپ باز می‌شود ولی از runner نه، فایروال میزبان محدود به IPهای خاص است و باید محدودهٔ خروجی GitHub Actions (`https://api.github.com/meta`، فیلد `actions`) مجاز شود.
4. اگر پورت عوض شده، فقط متغیر `VPS_PORT` را به‌روز کنید؛ هیچ تغییر کدی لازم نیست.

**بهبود ابزار در همین تغییر:** پیش از هر اتصال SSH یک probe واقعی TCP با `timeout 20` اجرا می‌شود و در شکست، پیام `::error::` با همان دستورهای تشخیصی چاپ می‌کند؛ همهٔ فرمان‌های `ssh` هم `ConnectTimeout=20` و `ConnectionAttempts=1` گرفتند تا خطا در ۲۰ ثانیه روشن شود، نه پس از دو دقیقه با پیام گنگ.

## ۱۲) پس از بازکردن قواعد ufw: هنوز timeout

مالک روی میزبان حدود ۱۲۰ قاعدهٔ `ufw allow from <github-actions-cidr> to any port 33878` افزود و از رایانهٔ خودش `nc -vz` به `185.192.113.199:33878` **موفق** شد؛ اما اجرای سوم run ۲۴۰ (attempt ۳، ۱۹:۱۷ تا ۱۹:۱۹) بازهم با همان timeout دو‌دقیقه‌ای شکست خورد.

یعنی:
- مسیر از ISP مالک باز است،
- مسیر از runner گیت‌هاب بسته است،
- و افزودن قاعده‌های ufw به‌تنهایی مسئله را حل نکرد — پس یا ufw فعال نیست (قواعد بی‌اثرند) و فیلتر جای دیگری است (فایروال پنل/Plesk، ipset، fail2ban یا upstream میزبان)، یا قاعده‌ها پیش از یک DROP قبلی قرار نگرفته‌اند.

**بهبود تشخیص در همین تغییر:** مرحلهٔ probe اکنون سه چیز را چاپ می‌کند تا حدس زدن تمام شود:

| خروجی | معنا |
| --- | --- |
| `runner egress: <ip>` | همان آدرسی که باید در فایروال میزبان مجاز شود |
| نتیجهٔ probe روی `VPS_PORT` | آیا پورت استقرار باز است |
| نتیجهٔ probe روی پورت ۲۲ (و ۳۳۸۷۸ اگر متفاوت باشد) | اگر ۲۲ باز و پورت استقرار بسته است ⇒ فیلتر «per-port»؛ اگر هر دو بسته‌اند ⇒ آدرس/IP مبدأ فیلتر می‌شود |

به‌علاوه یک دستور جمع‌بندی برای میزبان پیشنهاد می‌شود که خروجی‌اش همهٔ حالت‌ها را روشن می‌کند:

```
{ ss -lntp | grep -E ':33878|:22'; ufw status verbose; iptables -S | head -30; fail2ban-client status sshd; } 2>&1 | tee /tmp/net-diag.txt
```

**آزمون مستقل پیشنهادی:** دسترسی به پورت از یک نقطهٔ سوم (نه ISP مالک، نه گیت‌هاب) — مثل `check-host.net/check-tcp` — نشان می‌دهد آیا پورت برای اینترنت باز است یا فقط برای ISP مالک.

### نکته‌های عملیاتی این دور

- `gh` روی VPS نصب نیست؛ `gh run rerun` و `scripts/approve-transition.sh` باید روی رایانهٔ خود مالک و از داخل پوشهٔ clone اجرا شوند (`cd` لازم است).
- خطای «run … cannot be rerun; its workflow file may be broken» در واقع یعنی **یک rerun دیگر همین حالا در حال اجراست**؛ اجرای سوم در همان لحظه فعال بود. محدودیت هم‌زمانی است، نه فایل شکسته.

## پیگیری Vault

نیازی شناسایی نشد؛ هیچ ادعا، شماره یا محتوای تازه‌ای منتشر نشد. این گزارش ثبت در Vault محسوب نمی‌شود.
