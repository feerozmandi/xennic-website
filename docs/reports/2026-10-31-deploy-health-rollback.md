# ادامهٔ کنترل سلامت و بازگشت پیش‌نمایش

- **تاریخ و مبنا:** ۲۰۲۶-۱۰-۳۱؛ [PR #11](https://github.com/feerozmandi/xennic-website/pull/11)، قرارداد `META-INT-140` v0.7.0 و دستور مالک برای عدم فعال‌سازی SSH/deploy تا تأیید مستقل fingerprint.
- **وضعیت مبنای پیشین:** هر سه job PR در head `0521ad2c9d3cf8f81957ed1f616f8c12eb26d45d` موفق و انتشار در PR skipped بود. نتیجهٔ CI تغییر حاضر را باید جداگانه بررسی کرد.

## کارهای انجام‌شده

- کنترل سلامت داخلی برای پروژه و مسیر Compose ثابت آماده شد: Docker health برای PostgreSQL و App، `SELECT 1` در DB و `/health` از داخل کانتینر App؛ خطا و timeout با خروجی عمومی fail می‌شوند. این کنترل ثابت نمی‌کند Gate، TLS عمومی، API و مرورگر صحیح‌اند. اجرای واقعی همین کنترل در stack دورریختنی CI، هم در آزمون production و هم بعد از انتشار digest، به workflow افزوده شد؛ نتیجهٔ اجرای جدید هنوز باید در GitHub مشاهده شود.
- منطق مستقل تراکنش release و بازگشت آماده شد: اعتبارسنجی manifest، قفل، رد اجرای قدیمی یا وضعیت blocked، preflight، backup/restore تأییدشده پیش از migration، بررسی به‌روز بودن مجدد پیش و پس از migration، ثبت حالت مسدود پیش از تغییر و تأیید سلامت پیش از ثبت healthy. شکست پس از تلاش برای تعویض، فقط در صورت اثبات قبلی سازگاری schema مجاز به بازگرداندن image قبلی و آزمون سلامت آن است؛ شکست migration یا بازگشت نامطمئن نیازمند بررسی می‌ماند. اگر commit در حین migration قدیمی شود، traffic تغییر نمی‌کند و وضعیت برای بررسی مسدود می‌ماند.
- آزمون‌های synthetic ترتیب عملیات، شکست backup/migration/activation/health، ناسازگاری rollback، هم‌زمانی قفل و داده‌های نامعتبر را بررسی می‌کنند. این منطق **به backend عملیاتی، backup واقعی، قفل واقعی VPS، receiver یا workflow deploy متصل نیست**؛ در نتیجه هنوز اسکریپت استقرار کامل یا rollback عملیاتی محسوب نمی‌شود.
- workflow انتشار فقط پس از سه آزمون موفق push به `dev` ایمیج را با `GITHUB_TOKEN` و مجوز job محدود `packages: write` به GHCR می‌فرستد و همان digest را آزمون می‌کند. اجرای PR نه package-write می‌گیرد نه تصویر منتشر می‌کند. برای GHCR به‌طور معمول Secret تازه‌ای تعریف نشده است؛ امکان ساخت package و اولین انتشار با تنظیمات واقعی GitHub هنوز اثبات نشده و در صورت محدودیت package، مجوز repository باید بررسی شود.

## موارد باز

- fingerprint مستقل هنوز تأیید نشده و SSH/deploy خودکار فعال نیست. مقصد backup موجود، دسترسی/retention و restore واقعی نیز مشخص نیستند؛ تغییر داده پیش از backup سالم و restore جداگانه مجاز نیست.
- backend ممتاز و محدود، بررسی اعتبار artifact و branch، journal پایدار، backup خارجی، migration سازگار، سوییچ سرویس، rollback واقعی، Gate و تست عمومی هنوز اجرا یا تأیید نشده‌اند. هیچ تغییر VPS، DNS یا سرویس موجود انجام نشده است.

## Vault

قرارداد مرجع در Vault تغییر نکرد؛ شواهد بعدی در نشست Vault جداگانه پیگیری می‌شوند.

### نتیجهٔ اجرای GitHub در همین نشست

[PR #11](https://github.com/feerozmandi/xennic-website/pull/11) پس از موفقیت هر سه job در [CI 41194570589](https://github.com/feerozmandi/xennic-website/actions/runs/41194570589) با merge commit `397d505e4214f8c5c2270189ae8e7384905609ec` در `dev` ادغام شد. هر سه job همان commit و job انتشار در [CI 41194829543](https://github.com/feerozmandi/xennic-website/actions/runs/41194829543) موفق شدند: انتشار GHCR، دریافت digest منتشرشده بدون rebuild، آزمون production و کنترل سلامت داخلی در runner، و ثبت مرجع در Summary موفق بود. `GITHUB_TOKEN` کافی بود؛ Secret جدید برای این انتشار لازم نشد. API package برای این integration مجوز خواندن نداد؛ digest را از Summary همان اجرا ببینید و دسترسی pull سرور را جداگانه بررسی کنید. هیچ اتصال یا استقرار VPS انجام نشد.
