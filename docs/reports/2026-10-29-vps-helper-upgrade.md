# گزارش توسعه: ارتقای helperهای VPS

- **تاریخ گزارش:** ۲۰۲۶-۱۰-۲۹، تاریخ نشست؛ ساعت محیط اجرا و GitHub در بررسی قبلی ۲۰۲۶-۱۱-۰۸ نشان داده و اختلاف تأیید نشده است.
- **مبنای بررسی:** `dev` در `b21908ebad09ab0c5dcda7abb461846758c5b379`، [PR #17](https://github.com/feerozmandi/xennic-website/pull/17)، و خروجی گزارش‌شدهٔ مالک از `server2085`.
- **وضعیت تغییر:** ارتقای installer بر اساس خروجی SSH مالک موفق گزارش شد؛ عامل دسترسی مستقیم SSH ندارد.

## خلاصهٔ مدیریتی

مالک قبل از ارتقا تطبیق کامل helperها با نسخهٔ `449a135` و موفقیت `FixedRunner.verify_helpers` را گزارش کرد. آماده‌سازی فایل‌های نسخهٔ جدید با کنترل hash موفق شد؛ اجرای دوبارهٔ همان آماده‌سازی به علت وجود staging متوقف شد. سپس مالک اجرای installer با `--upgrade` را گزارش کرد و خروجی آن `Fixed preview helpers upgraded; previous helpers preserved; no deployment started.` بود.

## اقدامات و خروجی‌ها

- installer نسخهٔ `6442d6c56cbfe271c9dd0dde114f39deee4716588081e5667a1bba6b42a6cf98`، helperهای شناخته‌شدهٔ قدیمی و جدید، مجوزها و aliasها، وضعیت اولیه و قفل استقرار را کنترل کرده و نسخهٔ قبلی را نگه می‌دارد؛ rollback خطاهای قابل‌دریافت آزموده شده است. در قطع برق و سایر وقفه‌های غیرقابل‌دریافت، بررسی امن لازم است.
- گزارش مالک شاهد ارتقای helper است، نه راه‌اندازی app، DB، Caddy یا gate. تنظیمات، secrets، journal، DB و volume موضوع حذف یا بازنویسی دستور ارتقا نبودند. بررسی پس از ارتقا توسط مالک تطبیق helper جدید و نسخهٔ قبلی، `FixedRunner.verify_helpers`، نبود state/work و منابع پروژه، صحت ساختار مقدماتی env، سیاست backup و fingerprint را موفق گزارش کرد؛ در آن لحظه Compose و runtime OAuth غایب و فایل credential از نظر metadata خصوصی بود. سپس مالک ایجاد انحصاری Compose از قالب دارای hash و موفقیت preflight نصب نخست را بدون راه‌اندازی سرویس گزارش کرد. بررسی ساختار، صحت عملی credentials، انتقال backup، restore یا حفاظت واقعی را ثابت نمی‌کند.
- image منتخب `ghcr.io/feerozmandi/xennic-website@sha256:6761859cd3c9f3e6cd34c50cb9cbd4aa4970a87d78e874f42fa630f4a2eba07e`؛ [انتشار و pull در CI](https://github.com/feerozmandi/xennic-website/actions/runs/42516811740) و [verifier مستقل](https://github.com/feerozmandi/xennic-website/actions/runs/42517862088/job/128844728020) موفق، اما pull و verifier در VPS هنوز اثبات نشده‌اند. هر تغییر بعدی نوک `dev` به انتشار و تأیید دوباره نیاز دارد.
- در [CI بعدی](https://github.com/feerozmandi/xennic-website/actions/runs/42519732616/job/128850377596)، آزمون ارتقای installer موفق بود ولی بررسی یک‌بارمصرفِ hardcoded برای commit قدیمی `f18b315` پس از حرکت `dev` شکست خورد. مرحلهٔ موقتِ منقضی از workflow در این PR حذف شد؛ `scripts/preview-release-verifier.py`، کنترل واقعی آن در helperها، آزمون‌های verifier و انتشار/pull دست‌نخورده‌اند. نتیجهٔ CI اصلاح‌شده در انتظار بررسی است.

## آزمون‌ها و شواهد

| آزمون | محیط | نتیجه |
|---|---|---|
| [installer و زنجیره](https://github.com/feerozmandi/xennic-website/actions/runs/42516256065) | runner دورریختنی | موفق، شامل نسخهٔ قبلی، خطا و rollback؛ مستقل از نتیجهٔ VPS |
| تطبیق helper قبلی | SSH مالک | `HELPERS_VERSION=449a135 VERIFY_HELPERS=PASS` |
| staging و upgrade | SSH مالک | `UPGRADE_STAGING=PASS`؛ اجرای دوم staging متوقف؛ installer ارتقا و حفظ قبلی را موفق و عدم deployment را گزارش کرد. |
| بررسی پس از ارتقا | SSH مالک | `HELPERS_AND_PREVIOUS=PASS`, `INITIAL_STATE=PASS`, `PREVIEW_ENV=PASS`, `BACKUP_POLICY=PASS`, `HOST_FINGERPRINT=PASS`؛ ابتدا `COMPOSE=ABSENT`, `OAUTH_RUNTIME=ABSENT`, `OAUTH_CREDENTIALS=SAFE_FILE`. |
| آماده‌سازی Compose | SSH مالک | `COMPOSE_PREPARED=PASS INITIAL_PREFLIGHT=PASS; no service started`؛ شاهد صحت مسیر اولیه است، نه اجرای app یا پذیرش gate. |

## ریسک‌ها و کارهای باز

- **تعارض معماریِ نیازمند تعیین تکلیف مدیریت پروژه:** §۱۰.۲ و §۱۰.۴ مرجع `META-INT-140` صریحاً انتشار پورت App روی میزبان را ممنوع می‌کنند؛ اما helper ثابت `assert_initial_pristine` دقیقاً یک انتشار `127.0.0.1:<port>:3000` برای App را الزام می‌کند. آدرس loopback اینترنت عمومی نیست، اما همچنان پورت منتشرشدهٔ میزبان است و تأیید ضمنی این استثنا یا امن‌بودن مسیر اتصال Caddy محسوب نمی‌شود. Compose آماده‌شده غیرفعال است. تا رفع رسمی تعارض در قرارداد و اعمال/آزمون مسیر سازگار، App/DB یا gate شروع نمی‌شوند؛ کنترل helper دور زده نمی‌شود.
- runtime OAuth و توپولوژی Caddy و مسیر امن به app هنوز ساخته و اثبات نشده‌اند. پیش از Caddy، تداخل پورت‌های ۸۰ و ۴۴۳ باید دوباره بررسی شود؛ نباید به سایر سرویس‌ها یا داده‌های VPS دست زد. TLS، gate واقعی، Staff، API، media، GHCR در VPS و پذیرش مرورگر هنوز بررسی نشده‌اند. backup موقت دستی صرفاً برای staging بدون دادهٔ واقعی است؛ production به backup خودکار خارج VPS نیاز دارد.

## تصمیم‌ها و درخواست از مدیرکل

تغییر installer از قبل تأیید شده است. تعارض انتشار loopback با منع صریح پورت میزبان، همراه با مسیر امن gate به app، باید طبق دستور مالک برای تعیین تکلیف به مدیریت پروژه و مرجع Vault ارجاع شود؛ هیچ استثنایی فرض یا کنترل ایمنی دور زده نمی‌شود. در مسیر DNS، تنها تأیید رسمی نشانی امن پنل و محل مدیریت zone از پشتیبانی لازم است؛ تا احراز zone معتبر رکوردی تغییر نمی‌کند و nameserverها تغییر نمی‌کنند.

## پیگیری Vault

تعارض الزام loopback در helper با منع پورت میزبان در §۱۰.۲ و §۱۰.۴ `META-INT-140` باید برای تصمیم مدیریت پروژه و اصلاح/توضیح مرجع در نشست Vault پیگیری شود؛ Vault در این نشست فقط خواندنی است و این گزارش جایگزین مرجع نیست.
