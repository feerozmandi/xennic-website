# گزارش توسعه: انتشار اصلاح installer

- **تاریخ گزارش:** ۲۰۲۶-۱۰-۲۹، تاریخ نشست؛ ساعت محیط اجرا و GitHub تاریخ ۲۰۲۶-۱۱-۰۸ نشان داده و اختلاف تأیید نشده است.
- **مبنای بررسی:** [PR #17](https://github.com/feerozmandi/xennic-website/pull/17) ادغام‌شده و `dev` در `b21908ebad09ab0c5dcda7abb461846758c5b379`.
- **وضعیت تغییر:** ثبت شواهد و تأیید جداگانهٔ artifact در CI؛ کد installer اینجا تغییر نکرده است.

## خلاصهٔ مدیریتی

installer محدود در PR #17 ادغام شد. در [CI نهایی](https://github.com/feerozmandi/xennic-website/actions/runs/42516256065) آزمون‌های ارتقای واقعی helper نسخهٔ قدیم، refusal، lock، failure و rollback و زنجیرهٔ نصب‌شده با دادهٔ دورریختنی موفق شدند. هنوز هیچ تغییری روی VPS در این نشست انجام نشده است.

## اقدامات و خروجی‌ها

[انتشار dev](https://github.com/feerozmandi/xennic-website/actions/runs/42516811740) موفق شد؛ image و pull با helper نصب‌شده از همان digest در runner آزمایش شدند و artifact `13631194364` موجود است. صفحهٔ بستهٔ GitHub، image `ghcr.io/feerozmandi/xennic-website@sha256:6761859cd3c9f3e6cd34c50cb9cbd4aa4970a87d78e874f42fa630f4a2eba07e` و manifest معماری `linux/amd64` به digest `sha256:3d5d964cc1b6c811125fef76d8e7dac6737989abf143284ef1035dfc06fc3726` را نشان می‌دهد. metadata صفحه به‌تنهایی اثبات artifact نیست؛ verifier مستقل همان سیستم در CI جداگانه اجرا می‌شود. آزمون‌های GitHub به معنای استقرار VPS نیستند.

## آزمون‌ها و شواهد

| آزمون | محیط | نتیجه |
|---|---|---|
| ارتقای installer و زنجیرهٔ نصب‌شده | [CI PR #17](https://github.com/feerozmandi/xennic-website/actions/runs/42516256065) | موفق، داده و endpoints دورریختنی |
| انتشار و pull image | [CI dev](https://github.com/feerozmandi/xennic-website/actions/runs/42516811740) | موفق، commit بالا و artifact محفوظ |
| verifier مستقل | PR صرفاً تأیید شاهد | در انتظار نتیجه؛ دریافت artifact در Arena به محدودیت شبکه خورد |
| VPS | این نشست | اجرا یا تغییر جدید انجام نشد؛ نسخهٔ نصب‌شده در حال حاضر تأیید نشده است. |

## ریسک‌ها و کارهای باز

وضعیت واقعی helperها و محیط VPS باید با اجرای فقط‌خواندنی مالک بررسی شود. ارتقا فقط روی وضعیت نخستین بدون state و منابع preview کار می‌کند و هر حالت ناشناخته را رد می‌کند. نصب، credential، journal، DB و volume دست نخورده‌اند. پیش از Caddy تداخل پورت‌ها مجدداً بررسی شود؛ gate واقعی، TLS، صفحات و API و backup/restore و پذیرش مرورگر هنوز باز است. برای production، backup خودکار خارج VPS لازم است.

## تصمیم‌ها و درخواست از مدیرکل

اجرای بررسی فقط‌خواندنی از SSH مالک برای اطلاع از نسخهٔ روز VPS لازم است. برای DNS، فقط تأیید رسمی نشانی امن پنل و محل مدیریت zone از پشتیبانی لازم است؛ پیش از احراز zone هیچ رکوردی تغییر نمی‌کند و nameserver تغییر نمی‌کند.

## پیگیری Vault

تصمیم معماری جدیدی شناسایی نشد؛ پیگیری‌های قبلی Vault حفظ می‌شوند و این گزارش جایگزین مرجع نیست.
