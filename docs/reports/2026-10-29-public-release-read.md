# بررسی دسترسی عمومی انتشار پیش‌نمایش — ۲۰۲۶-۱۰-۲۹

مرجع تصمیم‌ها Vault، به‌ویژه `META-INT-140` v0.7.0 است؛ این گزارش تصمیم معماری جدید نیست. ساعت محیط و GitHub تاریخ متفاوتی نشان داده و اختلاف هنوز تأیید نشده است.

## شواهد

- [PR #21](https://github.com/feerozmandi/xennic-website/pull/21) با merge commit `09a9d00f25cee181a24fa39d645256869b6dc221` ادغام شد. [انتشار run 151](https://github.com/feerozmandi/xennic-website/actions/runs/42642887548) و [verifier مستقل](https://github.com/feerozmandi/xennic-website/actions/runs/42645113218/job/129256180630) برای digest `sha256:9e70bfceebafb0dd83152fb09f2e4d34b2e109497c34a1dad827e5046a31071f` موفق بودند. verifier با credential runner اجرا شد، نه بی‌نام روی VPS.
- مالک ارتقای محدود helper و بررسی پیکربندی، backup policy، gateway preflight و pull همان digest روی VPS را موفق گزارش کرد. این‌ها به معنای استقرار یا ورود واقعی نیستند. نتیجهٔ دریافت artifact بی‌نام از VPS هنوز نرسیده است.
- ساخت Environment `preview` با دسترسی اتصال موجود GitHub با 403 متوقف شد؛ از مالک ایجاد محیط محدود به شاخهٔ `dev` بدون افزودن secret درخواست شده است. نتیجه هنوز نرسیده است.

## تغییر محدود

مقدار صریح غیرمحرمانهٔ `public-read` در خط credential موجود، verifier را بدون Authorization به API ثابت GitHub متصل می‌کند و pull را با Docker config خالی و بدون login انجام می‌دهد. endpoint و redirect محدود، بررسی commit جاری، run موفق، artifact، digest و معماری باقی‌اند؛ credential نامعتبر هیچ fallback بی‌نامی ندارد و خطای دسترسی همچنان توقف است. این مقدار نه credential است و نه اثبات دسترسی عمومی. برای حالت خصوصی، دسترسی‌های API و GHCR باید جداگانه تعیین شوند؛ این تغییر راه‌حل عملیاتی credential خصوصیِ مستقل ارائه نمی‌کند.

آزمون واحد محلی با پاسخ‌های مصنوعی برای حالت عمومی، redirect و رد fallback اجرا شد. job موقت PR برای verifier بی‌نام واقعی و آزمون pull بی‌نام digest منتشرشده در publication پس از merge تعریف شده‌اند؛ نتیجهٔ CI و آزمون VPS در زمان نگارش مشخص نیست. CI جایگزین آزمون VPS نیست. این تغییر به‌تنهایی دستور استقرار، راه‌اندازی سرویس یا upgrade روی VPS نیست؛ installer موجود هنوز مسیر ارتقا از نسخهٔ نصب‌شدهٔ `09a9d00` به این نامزد را فراهم نمی‌کند. backend و receiver همچنان غیرفعال‌اند.

## پیگیری و ریسک

تکمیل و آزمون محدود activation، نصب/ارتقای محافظت‌شده، کلید SSH محدود و workflow وابسته به محیط، verifier نوک dev بعد از هر merge، backup/restore واقعی و نخستین استقرار تحت نظارت باقی‌اند. DNS، HTTPS و OAuth واقعی و پذیرش دو دستگاه اثبات نشده‌اند. انتقال و restore واقعی backup محلی age به رایانه هنوز اثبات نشده؛ پیش از production به مقصد خودکار خارج VPS نیاز است. اگر دسترسی بی‌نام واقعی شکست بخورد، آن مسیر متوقف و نیاز حداقلی API و GHCR جداگانه بررسی می‌شود. تغییرات و ابهام‌های مؤثر باید در نشست مستقل Vault پیگیری شوند؛ در این نشست Vault تغییر نکرد.
