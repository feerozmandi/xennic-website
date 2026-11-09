# پیگیری انتشار پیش‌نمایش پس از PR 23 — ۲۰۲۶-۱۰-۲۹

مرجع تصمیم‌ها Vault، به‌ویژه `META-INT-140` v0.7.0 است؛ این گزارش تصمیم معماری جدید نیست. ساعت GitHub با تاریخ نشست اختلاف نشان می‌دهد و اختلاف تأیید نشده است.

[PR #23](https://github.com/feerozmandi/xennic-website/pull/23) در `ac926714533265677a09a33a8185ae0e64f59c3a` به `dev` ادغام شد و [انتشار run 160](https://github.com/feerozmandi/xennic-website/actions/runs/42667416928) با شش job، شامل آزمون همان image و helper pull، موفق بود. artifact انتشار `13698162091` موجود و منقضی نشده است؛ hash artifact برابر digest image نیست. verifier مستقل همان نسخه در حال بررسی است و به‌تنهایی به معنی استقرار VPS یا پذیرش OAuth نیست.

مالک `PUBLIC_RELEASE_EVIDENCE=FAIL` را برای آزمون بی‌نام VPS گزارش کرد و Environment `preview` را ساخت؛ API تنظیم branch policy فقط برای `dev` را تأیید کرد. دستیابی به artifact در runner بی‌نام نیز قبلاً 401 داده بود؛ به credential موقت و فقط‌خواندنی Actions برای API نیاز است، نه فرض دسترسی مشترک API و GHCR. نصب/ارتقای نسخهٔ جدید روی VPS، provision حساب SSH محدود، workflow استقرار و نخستین اجرا هنوز انجام نشده‌اند. DNS معتبر، HTTPS و OAuth واقعی و بازیابی backup روی VPS تأیید نشده‌اند.

پیگیری: پس از verifier نوک فعلی dev، اتصال SSH و workflow باید با کلید اختصاصی در Environment و fingerprint تأییدشده و بدون دسترسی secret برای PRهای نامطمئن تکمیل و در CI بررسی شود؛ سپس ارتقای محافظت‌شدهٔ installer و نخستین استقرار تحت نظارت، backup/restore و سلامت gate انجام شود. تنظیم DNS فقط پس از تأیید پنل امن رسمی و صرفاً رکورد مجاز preview انجام می‌شود. پیش از production، backup خودکار خارج VPS لازم است. پیگیری تصمیم‌ها و ابهام‌های مؤثر در نشست مستقل Vault انجام شود؛ Vault در این نشست تغییر نکرد.
