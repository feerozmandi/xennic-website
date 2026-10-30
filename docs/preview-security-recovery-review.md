# بررسی امنیت و بازیابی پیش‌نمایش

**وضعیت: بررسی آزمایشی، نه تأیید استقرار.** مقصد مدنظر `https://preview.xennic.ir` است، اما طرح حفاظت و proxy نهایی هنوز انتخاب نشده‌اند. هیچ ارتباط یا تغییر VPS/DNS در این نشست مجاز نیست. مبنای کد `dev` در `befba690d5d58eed97c8707092d7c203aad0b188` و Vault خواندنی `dev` در `c51e087f206b235987987906c62ea4a0ed689967` است.

## بازیابی داده در محیط دورریختنی

اسکریپت `scripts/ci-restore.sh` فقط در CI با project نام‌گذاری‌شدهٔ آزمایشی کار می‌کند. داده‌های مصنوعی را از PostgreSQL با `pg_dump --format=custom` و از volume media با tar ثبت و به یک **Compose project، پایگاه‌داده، شبکه و volume مجزای تازه** بازمی‌گرداند. پس از restore و اجرای مجدد migration، بررسی عملی شامل ورود Staff بازیابی‌شده، API و نمایش ویرایش CMS، SHA-256 فایل media دریافت‌شده از برنامه و ردیف `shared.customers` است. فایل‌های تست و credential تصادفی موقتی‌اند و پس از تست پاک می‌شوند؛ دادهٔ واقعی استفاده نمی‌شود. نتیجهٔ واقعی CI در [گزارش این نشست](reports/2026-10-30-preview-recovery-security.md) ثبت می‌شود.

این یک تست بازیابی محلی/CI است، نه برنامهٔ backup عملیاتی. dump سازگار تراکنشی است، اما archive فایل و DB هم‌زمان و اتمیک نیستند؛ تست هنگام نبود نوشتن اجرا می‌شود. برای محیط واقعی لازم است توقف نوشتن یا مکانیزم snapshot سازگار، رمزنگاری پیش از انتقال، کلید و سطح دسترسی، مقصد خارج VPS، retention، RPO/RTO، آزمون دوره‌ای restore و روش تضمین پیوند DB/media تعیین و تأیید شود. برای بازیابی auth، نسخهٔ برنامه/Schema و نگهداری امن secret سازگار نیز لازم است. `down --volumes` فقط در projectهای دورریختنی CI استفاده می‌شود و برای دادهٔ واقعی ممنوع است.

## Origin، CSRF و کوکی: یافته‌های فعلی

این بخش نتیجهٔ بازبینی نسخهٔ Payload 3.91.0 و پیکربندی فعلی است، نه تنظیمات نهایی:

- `serverURL`، `csrf` و `cors` در `src/payload.config.ts` مشخص نشده‌اند؛ مقادیر پیش‌فرض به‌ترتیب رشتهٔ خالی، فهرست خالی و فهرست خالی‌اند. `getRequestOrigin` تنها origin مورد اعتماد را از allowlist می‌پذیرد و در نبود آن fallback خالی می‌دهد. تنظیم صریح URL معتبر preview باید با طرح proxy نهایی تأیید و آزموده شود؛ فهرست خالی CORS نباید به‌عنوان پیکربندی نهایی قلمداد شود.
- Staff از پیش‌فرض Payload استفاده می‌کند: کوکی session، `HttpOnly`، `SameSite=Lax` و `Secure=false` است؛ domain تنظیم نشده است. برای HTTPS واقعی، `Secure` و scope مناسب باید صریحاً طراحی/آزموده شوند؛ `HttpOnly` مانع CSRF نیست. هیچ ادعای تست مرورگر و TLS واقعی نداریم.
- در `payload/dist/auth/extractJWT.js`، اگر `csrf` خالی باشد، cookie token با Origin دلخواه هم پذیرفته می‌شود. تست characterization همان رفتار را با cookie معتبر و Origin نامرتبط بررسی می‌کند؛ این **نقطهٔ باز و مانع استقرار** است، نه ویژگی مطلوب. با `csrf` غیرخالی، Origin بررسی می‌شود و درخواست بدون Origin به `Sec-Fetch-Site` وابسته است؛ این کنترل عمدتاً مسیر cookie را در بر می‌گیرد و به‌تنهایی policy کامل همهٔ مسیرها، Bearer، login یا browser را تضمین نمی‌کند. تغییر و آزمون policy واقعی باید قبل از استقرار انجام شود.
- proxy واقعی باید TLS و Host/Origin معتبر را پایان‌دهی کند، هدرهای `Forwarded` و `X-Forwarded-*` غیرقابل‌اعتماد را پاک/بازنویسی کند، upstream را از bypass شبکه‌ای IPv4/IPv6 حفظ کند و cookie، Bearer و مسیرهای admin، REST/GraphQL، media و health را بدون نشت اطلاعات درست منتقل کند. روی مکانیزم trust proxy و تشخیص scheme/host توسط Next/Payload نباید بدون تست فرض کرد. Caddy فعال قبلاً پیدا نشده و هنوز انتخابی نهایی نیست.
- Basic Auth در لایهٔ ورودی و Payload Bearer هر دو از `Authorization` استفاده می‌کنند. تست قبلی نشان داد Basic gate هدر Bearer را رد می‌کند؛ کوکی Staff به‌همراه Basic می‌تواند کار کند، اما این به‌معنای پشتیبانی Bearer یا تأیید Basic به‌عنوان دروازهٔ نهایی نیست.

**وابسته به تصمیم:** انتخاب proxy و gate توسط مالک/زیرساخت، نحوهٔ اعتماد به هدرها، محدودهٔ مجاز Origin و cookie، دسترسی کاربران و حساب اول. پس از انتخاب، باید همان محصول و همان تنظیم gate در محیط مجزا به‌صورت HTTPS واقعی با مرورگر و HTTP client آزموده شود: origin مجاز/نامجاز و غایب، SameSite/Secure/HttpOnly، login/logout، admin، Server Actions، API cookie و Bearer، GraphQL، آپلود/خواندن media، spoofed forwarded headers، IPv4/IPv6 و عدم bypass. شبیه‌ساز `x-test-preview-key` آزمون آن محصول نیست و هرگز برای اینترنت مناسب نیست.

## بررسی نشت Secret در لاگ

`tests/log-security.mjs` در محیط Docker CI فقط داده و رمزهای **مصنوعی** می‌سازد، مسیرهای موفق و ناموفق login/API، migration، seed و اتصال ناموفق DB را اجرا می‌کند و خروجی migration/seed و لاگ برنامه را در حافظه برای canaryهای شناخته‌شده، شامل credential، توکن، کوکی، URL و نسخهٔ URL-encoded آن‌ها اسکن می‌کند. تست هیچ لاگ خام یا مقدار canary را چاپ یا به artifact تبدیل نمی‌کند. wrapper فعلی خروجی child migration/seed را دور می‌ریزد و خطاهای DB را با پیام عمومی گزارش می‌کند؛ این باعث محدودیت در عیب‌یابی هم هست.

اسکن رشته‌ای صرفاً همان سناریوها، قالب‌ها و لاگ‌های در دسترس را پوشش می‌دهد؛ نمی‌تواند نبود نشت در stack trace، dump، درخواست‌های دیگر، encoding متفاوت، Docker daemon، proxy، PostgreSQL، artifactهای خطا یا محیط واقعی را تضمین کند. باید logging و rotation و redaction محصول proxy و upstream و سناریوهای خطا پیش از هر دسترسی واقعی بررسی و با دادهٔ مصنوعی دوباره آزموده شوند. لاگ خام حاوی راز هرگز در Git یا گفتگو ارسال نشود.

## خلاصه برای دستیار زیرساخت

- تصویر Node `22.22.3-bookworm-slim` با Next.js/Payload 3.91.0، خروجی build خارج VPS و `next start`، پورت ۳۰۰۰ در شبکه داخلی؛ Compose فعلی صرفاً آزمایشی و bind آن loopback است، نه تنظیم proxy نهایی.
- PostgreSQL `16.14-bookworm` جدا از n8n و هر DB عملیاتی، schemaهای `website` و `shared`؛ volumeهای جدا برای DB و `/app/media`، کاربر داخلی کانتینر `node`. migration و seed تک‌اجرا با wrapper و قفل انجام می‌شوند؛ seed موجود را بازنویسی نمی‌کند. عدم سازگاری دیتابیس توسعه‌ای قدیمی باید جداگانه بررسی شود.
- ورودی‌های نمونه `.env.preview.example` شامل DB، `PREVIEW_DATABASE_URL` و `PREVIEW_PAYLOAD_SECRET` هستند؛ Secretها و فایل واقعی نباید در Git یا چت باشند. تنظیم صریح URL، cookie، CSRF و تنظیمات gate هنوز آمادهٔ تولید نیست.
- اندازهٔ مشاهده‌شدهٔ تصویر قبلی حدود ۴۶۱ MiB و build آزمایشی در CI حدود ۱۲۴ ثانیه بود؛ وابسته به محتوا، cache و معماری. برای عدد دقیق هر انتشار `docker image inspect` و digest همان image بررسی شود. نیاز build محلی خارج از VPS، فضای آزاد برای image، لایه‌های build، حجم DB/media و backup جداگانه سنجیده شود.
- معماری CPU و نسخهٔ Docker سرور، روش تأییدشدهٔ registry یا انتقال امن offline، امکان pull، محدودیت شبکه و چرخهٔ به‌روزرسانی نامشخص‌اند. گزینه‌های registry یا انتقال آرشیو قابل‌بررسی‌اند ولی **هیچ مقصدی انتخاب نشده**؛ نسخهٔ مشخص و digest/manifest و اصالت artifact پس از انتقال تأیید شود. کانال انتقال و نگهداری backup باید محرمانگی و تمامیت داشته باشد. هیچ تصویر، داده یا credential اکنون به VPS منتقل نشده است.
- ظرفیت گزارش‌شدهٔ سرور ۴ CPU، حدود ۵٫۸ GiB RAM و نمونهٔ ۱٫۷ GiB در دسترس است؛ این داده کفایت را اثبات نمی‌کند. سقف و اوج منابع، proxy، simultaneous restore، دیسک و پایش پیش از استقرار تعیین شوند.
