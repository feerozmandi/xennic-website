# ادامهٔ مسیر اجرایی پیش‌نمایش

- **تاریخ:** ۲۰۲۶-۱۰-۳۱؛ مبنا [PR #13](https://github.com/feerozmandi/xennic-website/pull/13)، آزمون کد commit `d307f4c6db062ac9bbba771cdc4b2d003561e8fc`.
- **خلاصه:** عملیات تعویض محدود Compose و یک primitive آزمایشی رمزنگاری با دادهٔ مصنوعی افزوده شد. هیچ backend ممتاز عملیاتی نصب یا فعال نشده است؛ این تغییرات هنوز جای مقصد backup، helper کامل یا تأیید هویت SSH را نمی‌گیرند.

## اقدامات و شواهد

- تابع تعویض app فقط manifest معتبر، مخزن ثابت، digest و فرمان Compose ثابت را می‌پذیرد؛ activation و rollback تصویر سازگار از همان عملیات استفاده می‌کنند. این ماژول به‌تنهایی CLI ممتاز یا deployment نیست و نیازمند پیکربندی و فایل‌های مورد اعتماد root و اتصال امن به backend است.
- نمونهٔ AES-256-GCM برای آزمون مصنوعی DB و media: کلید تصادفی موقت، header و نوع authenticated، رد تغییر و انتشار بدون overwrite پس از احراز tag. محتوای رمزگشایی‌شده پیش از تأیید tag موقتاً در فایل `0600` در پوشهٔ خصوصی ذخیره می‌شود. فایل dump اولیه در آزمون CI plaintext است. این فرمت آزمایشی جایگزین تأییدشدهٔ پیشنهاد `age` نیست، key management، اتصال DB/media به شناسهٔ مشترک snapshot، محافظت در برابر تغییر هم‌زمان ورودی و ذخیره‌سازی خارج VPS ندارد و برای دادهٔ واقعی آماده نیست.
- `ci-restore.sh` برای داده‌های مصنوعی آن دو فایل را رمز/رمزگشایی و به پروژهٔ جدا restore می‌کند و reject فساد را قبل از restore می‌آزماید. سپس adapter ویژهٔ CI با journal و transaction واقعی، ایمیج عمداً خراب را با Compose اجرا و همان عملیات تعویض را برای تصویر قبلی سازگار فراخوانی می‌کند؛ پس از آن داده، سلامت و blocked بررسی می‌شوند. تصمیم سازگاری، اتصال backup و mapping ایمیج این adapter مصنوعی‌اند؛ آزمایش backend ممتاز یا اعتبار GHCR نیست.
- آزمون‌های محلی ۲۰۲۶-۱۰-۳۱: تست primitive و ۵۸ تست Python موجود/جدید، بررسی syntax و `git diff --check` موفق. Docker در Arena اجرا یا نصب نشد. در [CI 41213163176](https://github.com/feerozmandi/xennic-website/actions/runs/41213163176) برای commit `d307f4c6db062ac9bbba771cdc4b2d003561e8fc` هر سه job از جمله production-preview موفق شدند؛ انتشار در PR غیرفعال بود. آن job مسیر رمزگذاری/بازیابی و تعویض/rollback ایزولهٔ بالا را اجرا کرد، نه helper ممتاز عملیاتی را.
- شاهد مستقل موجود انتشار: [CI موفق 41194829543](https://github.com/feerozmandi/xennic-website/actions/runs/41194829543) برای `397d505e4214f8c5c2270189ae8e7384905609ec`، `linux/amd64` و ایمیج `ghcr.io/feerozmandi/xennic-website@sha256:cf90f366125e89a970db679d98b74998a331c5ff77f6c3cb77d2db453c9e4363`؛ آن digest در همان CI از GHCR pull و آزموده و شناسهٔ ایمیج اجراشده کنترل شد. این شاهد اجرای قبلی است، نه verifier مستقل تعبیه‌شده در سرور یا اثبات deploy VPS.

## موانع و پیگیری

- helperهای ثابت ممتاز برای بررسی release/current، backup و verify، pull، migration، activation، health و rollback باید با مالکیت امن نصب، به controller متصل و روی stack دورریختنی از همان مسیر واقعی آزموده شوند. اعتبارسنجی ارتباط موفقیت run با commit/digest و pull/معماری/ایمیج در حال اجرا در backend هنوز پیاده نشده است.
- برای backup واقعی، قرارداد و ابزار عملیاتی سازگار با پیشنهاد موجود و تأییدشده، کلید و بازیابی امن، snapshot هماهنگ DB/media، مقصد خصوصی خارج سرور و restore مستقل لازم است؛ هیچ مقصدی موجود فرض نشده است. rollback تصویر به‌تنهایی migration ناسازگار را بازنمی‌گرداند.
- SSH و deploy غیرفعال‌اند؛ هیچ تغییر VPS، DNS یا Vault و هیچ secret عملیاتی استفاده نشد. موارد مالک در زمان مناسب فقط fingerprint مستقل، مقصد backup و ورود امن تنظیمات‌اند. مقصد و هر تصمیم معماری جدید در Vault جداگانه پیگیری شود؛ این گزارش جای Vault نیست.
