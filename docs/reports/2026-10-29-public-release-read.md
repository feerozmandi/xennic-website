# بررسی دسترسی انتشار پیش‌نمایش — ۲۰۲۶-۱۰-۲۹

مرجع تصمیم‌ها Vault، به‌ویژه `META-INT-140` v0.7.0 است؛ این گزارش تصمیم معماری جدید نیست. ساعت محیط و GitHub تاریخ متفاوتی نشان داده و اختلاف هنوز تأیید نشده است.

## شواهد

- [PR #21](https://github.com/feerozmandi/xennic-website/pull/21) با merge commit `09a9d00f25cee181a24fa39d645256869b6dc221` ادغام شد. [انتشار run 151](https://github.com/feerozmandi/xennic-website/actions/runs/42642887548) و [verifier مستقل](https://github.com/feerozmandi/xennic-website/actions/runs/42645113218/job/129256180630) برای digest `sha256:9e70bfceebafb0dd83152fb09f2e4d34b2e109497c34a1dad827e5046a31071f` موفق بودند. verifier از credential موقت runner استفاده کرد.
- مالک ارتقای محدود helper و بررسی پیکربندی، backup policy، gateway preflight و pull همان digest روی VPS را موفق گزارش کرد. این‌ها به معنای استقرار یا ورود واقعی نیستند.
- آزمون verifier بی‌نام واقعی در [CI 42661769448](https://github.com/feerozmandi/xennic-website/actions/runs/42661769448/job/129314894058) به HTTP 401 در endpoint دانلود artifact رسید، با وجود موفقیت بررسی tip؛ دریافت بی‌نام شاهد در آن runner ممکن نشد. پاسخ 302 مشاهده‌شده در Sandbox به‌تنهایی اثبات دانلود نبود. آزمون موقت برداشته شد، نه اینکه موفق تلقی شود؛ verifier اصلی با credential معتبر و کنترل‌های provenance و redirect حفظ شده است.
- مالک ساخت Environment `preview` و خروجی `PUBLIC_RELEASE_EVIDENCE=FAIL` را گزارش کرد. API گیت‌هاب تأیید کرد policy سفارشی فعال است و تنها قاعدهٔ آن شاخهٔ دقیق `dev` است. هیچ secretی از طریق این اتصال اضافه نشده است؛ علت دقیق شکست آزمون VPS از خروجی کلی معلوم نیست.

## تغییر محدود پیشنهادی

برای package عمومی، مقدار غیرمحرمانهٔ صریح `public-read` فقط در عملیات pull موجب استفاده از Docker config خالی و بدون login می‌شود؛ digest و معماری همچنان بررسی می‌شوند. backend پیشنهادی credential API را به pull ارسال نمی‌کند؛ شکست pull عمومی متوقف می‌کند و به credential API یا روش دیگری fallback نمی‌کند. دسترسی API و GHCR مستقل‌اند؛ در صورت خصوصی‌شدن GHCR باید دسترسی مستقل آن طراحی و تأیید شود. credential اشتباه در مسیر احراز هویت pull همچنان باعث شکست است و fallback بی‌نام ندارد. نام محیط قدیمی client (`PREVIEW_GHCR_TOKEN`) برای سازگاری حفظ شده اما در backend پیشنهادی فقط credential API را حمل می‌کند؛ ورود هیچ مقدار واقعی در Git یا گفتگو مجاز نیست.

آزمون واحد محلی با پاسخ‌های مصنوعی موفق بود؛ آزمون pull بی‌نام digest منتشرشده برای publication بعدی تعریف شده و [CI برای `77cf914`](https://github.com/feerozmandi/xennic-website/actions/runs/42662603367) با پنج job موفق پایان یافت. هیچ‌یک جایگزین آزمون VPS نیست.

در ادامهٔ پیش‌نویس، CLI همان backend و receiver به مسیر `run_checked` متصل و برای نصب نخستِ بدون journal مسیر upgrade محدود از helperهای دقیق `09a9d00` پیشنهاد شد. کنترل `FixedRunner.verify_helpers`، قفل، provenance، backup و rollback حفظ شده‌اند؛ کنترل ownership/mode برای receiver هم افزوده شد. آزمون واحد محلی و [پنج job در CI 42664722435 برای `afcdf64`](https://github.com/feerozmandi/xennic-website/actions/runs/42664722435) موفق شدند: upgrade با رد وضعیت ناشناخته و rollback آزمایشی، و نصب نخست از مسیر receiver نصب‌شده با GitHub/GHCR و دادهٔ مصنوعی. این آزمون به معنای SSH واقعی یا VPS نیست. هیچ‌یک روی VPS نصب یا فعال نشده و حساب محدود، sudo، کلید، workflow استقرار و اولین اجرای تحت نظارت هنوز آماده نیستند. پس از آماده‌شدن مسیر ایمن، استفاده از credential کوتاه‌عمر و فقط‌خواندنی Actions برای API بدون credential بلندمدت جداگانه باید عملیاتی آزموده شود.

## پیگیری و ریسک

تکمیل و آزمون محدود activation، نصب/ارتقای محافظت‌شده، کلید SSH محدود و workflow وابسته به محیط، verifier نوک dev بعد از هر merge، backup/restore واقعی و نخستین استقرار تحت نظارت باقی‌اند. DNS، HTTPS و OAuth واقعی و پذیرش دو دستگاه اثبات نشده‌اند. انتقال و restore واقعی backup محلی age به رایانه هنوز اثبات نشده؛ پیش از production به مقصد خودکار خارج VPS نیاز است. تغییرات و ابهام‌های مؤثر باید در نشست مستقل Vault پیگیری شوند؛ در این نشست Vault تغییر نکرد.
