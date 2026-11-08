# گزارش توسعه: ارتقای helperهای VPS

- **تاریخ گزارش:** ۲۰۲۶-۱۰-۲۹، تاریخ نشست؛ ساعت محیط اجرا و GitHub در بررسی قبلی ۲۰۲۶-۱۱-۰۸ نشان داده و اختلاف تأیید نشده است.
- **مبنای بررسی:** `dev` در `b21908ebad09ab0c5dcda7abb461846758c5b379`، [PR #17](https://github.com/feerozmandi/xennic-website/pull/17)، و خروجی گزارش‌شدهٔ مالک از `server2085`.
- **وضعیت تغییر:** ارتقای installer بر اساس خروجی SSH مالک موفق گزارش شد؛ عامل دسترسی مستقیم SSH ندارد.

## خلاصهٔ مدیریتی

مالک قبل از ارتقا تطبیق کامل helperها با نسخهٔ `449a135` و موفقیت `FixedRunner.verify_helpers` را گزارش کرد. آماده‌سازی فایل‌های نسخهٔ جدید با کنترل hash موفق شد؛ اجرای دوبارهٔ همان آماده‌سازی به علت وجود staging متوقف شد. سپس مالک اجرای installer با `--upgrade` را گزارش کرد و خروجی آن `Fixed preview helpers upgraded; previous helpers preserved; no deployment started.` بود.

## اقدامات و خروجی‌ها

- installer نسخهٔ `6442d6c56cbfe271c9dd0dde114f39deee4716588081e5667a1bba6b42a6cf98`، helperهای شناخته‌شدهٔ قدیمی و جدید، مجوزها و aliasها، وضعیت اولیه و قفل استقرار را کنترل کرده و نسخهٔ قبلی را نگه می‌دارد؛ rollback خطاهای قابل‌دریافت آزموده شده است. در قطع برق و سایر وقفه‌های غیرقابل‌دریافت، بررسی امن لازم است.
- گزارش مالک شاهد ارتقای helper است، نه راه‌اندازی app، DB، Caddy یا gate. تنظیمات، secrets، journal، DB و volume موضوع حذف یا بازنویسی دستور ارتقا نبودند. نتیجهٔ تازهٔ بررسی مستقلِ پس از ارتقا و آماده‌بودن تنظیمات هنوز دریافت نشده است.
- image منتخب `ghcr.io/feerozmandi/xennic-website@sha256:6761859cd3c9f3e6cd34c50cb9cbd4aa4970a87d78e874f42fa630f4a2eba07e`؛ [انتشار و pull در CI](https://github.com/feerozmandi/xennic-website/actions/runs/42516811740) و [verifier مستقل](https://github.com/feerozmandi/xennic-website/actions/runs/42517862088/job/128844728020) موفق، اما pull و verifier در VPS هنوز اثبات نشده‌اند. هر تغییر بعدی نوک `dev` به انتشار و تأیید دوباره نیاز دارد.

## آزمون‌ها و شواهد

| آزمون | محیط | نتیجه |
|---|---|---|
| [installer و زنجیره](https://github.com/feerozmandi/xennic-website/actions/runs/42516256065) | runner دورریختنی | موفق، شامل نسخهٔ قبلی، خطا و rollback؛ مستقل از نتیجهٔ VPS |
| تطبیق helper قبلی | SSH مالک | `HELPERS_VERSION=449a135 VERIFY_HELPERS=PASS` |
| staging و upgrade | SSH مالک | `UPGRADE_STAGING=PASS`؛ اجرای دوم staging متوقف؛ installer ارتقا و حفظ قبلی را موفق و عدم deployment را گزارش کرد. |
| بررسی پس از ارتقا | SSH مالک | در انتظار نتیجهٔ بررسی فقط‌خواندنی |

## ریسک‌ها و کارهای باز

آمادگی واقعی Compose، OAuth، GHCR، پشتیبان‌گیری/restore و حفاظت مستقل کامل نشده است. پیش از Caddy، تداخل پورت‌های ۸۰ و ۴۴۳ باید دوباره بررسی شود؛ نباید به سایر سرویس‌ها یا داده‌های VPS دست زد. TLS، gate واقعی، Staff، API، media و پذیرش مرورگر هنوز بررسی نشده‌اند. backup موقت دستی صرفاً برای staging بدون دادهٔ واقعی است؛ production به backup خودکار خارج VPS نیاز دارد.

## تصمیم‌ها و درخواست از مدیرکل

تغییر installer از قبل تأیید شده است؛ تأیید معماری تازه درخواست نمی‌شود. فقط‌خواندنی وضعیت پس از ارتقا از SSH مالک بررسی می‌شود. در مسیر DNS، تنها تأیید رسمی نشانی امن پنل و محل مدیریت zone از پشتیبانی لازم است؛ تا احراز zone معتبر رکوردی تغییر نمی‌کند و nameserverها تغییر نمی‌کنند.

## پیگیری Vault

تصمیم معماری جدید شناسایی نشد؛ پیگیری‌های قبلی Vault حفظ می‌شوند و این گزارش جایگزین مرجع Vault نیست.
