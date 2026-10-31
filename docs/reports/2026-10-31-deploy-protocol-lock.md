# ادامهٔ اجزای مستقل استقرار

- **تاریخ و مبنا:** ۲۰۲۶-۱۰-۳۱؛ [PR #11](https://github.com/feerozmandi/xennic-website/pull/11) و قرارداد `META-INT-140` v0.7.0.
- **وضعیت:** پیش از این تغییر، هر سه بررسی CI برای head `1be5c9b668af17c7b9390ef730873ee1ba55e5a2` موفق و job انتشار در PR skipped بود. تغییر حاضر در انتظار CI است.

## انجام‌شده

- parser سمت گیرندهٔ SSH، command ثابت، manifest، سقف اندازه و token را جدا از client کنترل و هر دادهٔ نامعتبر را بدون بازچاپ token رد می‌کند. سازگاری آن با payload واقعی client در تست synthetic بررسی شد. **گیرنده عمداً غیرفعال است، حتی ورودی معتبر را deploy نمی‌کند و نباید به‌عنوان forced-command نصب شود.**
- یک primitive قفل انحصاری `flock` برای مسیر قراردادی `/run/lock/xennic-preview-deploy.lock` آماده شد. مالکیت و نوع parent/file، symlink، hardlink و سطوح مجوز بررسی می‌شوند؛ قفل در صورت خروج از context آزاد می‌شود. تست چندفرایندی، رد فایل و parent نامطمئن و رفتار پس از آزادسازی در sandbox موفق بود.
- آزمون‌های manifest، client، receiver و lock در مجموع ۱۶ گروه unittest موفق بودند و در CI قرار گرفتند. این تست‌ها Docker، VPS، SSH واقعی، backup، migration یا سلامت نهایی را اجرا نمی‌کنند.

## محدودیت و گام بعد

- استفادهٔ واقعی از قفل باید در کل توالی backup، migration، health و rollback، هم در deploy خودکار و هم عملیات دستی، در receiver ممتاز و بازبینی‌شده برقرار شود؛ کد حاضر به‌تنهایی این یکپارچگی، ترتیب اجرا یا rollback را تضمین نمی‌کند. Forced-command، کنترل ورودی ممتاز، نگهداری وضعیت ترتیب release و fail-closed در خطا هنوز باید تکمیل و تست شوند.
- مالک endpoint/IP را تأیید و fingerprint عمومی ارائه کرده، ولی مستقل‌بودن منشأ fingerprint مشخص نشده است. نام/قابلیت فضای backup موجود، restore و دسترسی GitHub Actions به سرور هنوز روشن نیستند. هیچ Secret، تغییر VPS، DNS یا deploy انجام نشده است.

## Vault

`META-INT-140` مرجع قرارداد باقی می‌ماند؛ ثبت شواهد جدید در Vault نیازمند نشست جداگانه است و این نشست Vault را تغییر نداد.
