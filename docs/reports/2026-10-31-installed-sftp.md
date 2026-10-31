# ادامهٔ helper نصب‌شده و انتقال SFTP

- **تاریخ:** ۲۰۲۶-۱۰-۳۱؛ [PR #13](https://github.com/feerozmandi/xennic-website/pull/13). هیچ SSH عملیاتی، استقرار، تغییر VPS یا DNS انجام نشده است.
- **نتیجه:** helperهای ثابت `backup-verify` و انتقال SFTP و نصب‌کنندهٔ محدود اضافه شدند. `backup-verify` نام ثابت مورد استفادهٔ کنترل‌کننده است، اما سایر helperهای ضروری و زنجیرهٔ کامل هنوز فراهم نیستند؛ installer نیز sudoers یا SSH نصب نمی‌کند.

## تغییرات

- journal پیش از backup و هر maintenance احتمالی blocked می‌شود. شکست backup، عملیات بعدی را متوقف و وضعیت blocked را حفظ می‌کند؛ blocked به‌تنهایی به معنای توقف نویسنده‌ها نیست. توقف واقعی app، snapshot و wiring عملیاتی هنوز وجود ندارد.
- `scripts/preview-backup-sftp.py` فقط manifest محدود را از stdin می‌گیرد؛ ورودی دلخواه برای مسیر، host، argv یا محیط نمی‌پذیرد. پیکربندی root-owned شامل نام کاربر و پورت تأییدشده، مسیر ثابت SSH key و known_hosts، `StrictHostKeyChecking=yes` و SFTP batch بدون shell است. فایل age ثابت upload و مجدداً download و hash آن مقایسه می‌شود؛ رکورد hash در state root-owned ذخیره می‌شود. این رکورد امضای خارجی یا اثبات مقصد خارج VPS نیست و جای restore مستقل را نمی‌گیرد.
- `scripts/install-preview-sftp-helper.py` فقط staging ثابت و root-owned `/root/xennic-preview-install` را می‌خواند، ورودی ندارد، نصب موجود را بازنویسی نمی‌کند و helperهای backup و SFTP را root-only در `/usr/local/libexec/xennic-preview` قرار می‌دهد. تا تکمیل installer کلی این مسیر برای نصب استقرار کامل نیست.
- job `installed-sftp` در runner دورریختنی GitHub یک SSH/SFTP server مستقل با کلید آزمایشی اجرا می‌کند و کد را root-owned stage و نصب می‌کند. [اجرای 41216606213](https://github.com/feerozmandi/xennic-website/actions/runs/41216606213) فقط انتقال، readback و شکست SFTP را با helper نصب‌شده آزمود. گسترش همان job برای آزمون `backup-verify` با PostgreSQL و برنامهٔ واقعی و شکست انتقال در انتظار CI commit بعدی است. منبع release مصنوعی است؛ هیچ‌یک آزمون verifier انتشار، مهاجرت یا کل backend نیست. انتشار در dev وابسته به موفقیت این job نیز شد.
- آزمون‌های Python transaction، backend و readiness محلی موفق شدند؛ Docker و SSH عملیاتی در Arena اجرا نشدند. نتیجهٔ job جدید در CI همین PR پیگیری می‌شود.

## مانع‌ها و راه‌حل بعدی

- **کد:** `backup-verify` برای پروژهٔ ثابت فقط در صورت وجود دو سرویس app و postgres، توقف app، نبود سایر کانتینرهای پروژه یا دارای دسترسی به volume/network DB و نبود اتصال DB دیگر، dump/media را با age بسته‌بندی، SFTP و readback را اجرا و DB را در کانتینر PostgreSQL دورریختنی بدون شبکه restore می‌کند. این کد هنوز در CI جدید تأیید نشده و پوشش دسترسی مستقیم فرایندهای خارج Docker نیازمند بازبینی میزبان است؛ صرف blocked یا ادعای توقف کافی نیست. در شکست app عمداً متوقف و journal blocked باقی می‌ماند.
- **کد:** helperهای release-check/current/pull/migrate/activate/health/rollback و installer یکپارچه هنوز آماده نیستند. verifier باید به run موفق و artifact همان commit متصل شود؛ مهاجرت ناشناخته یا بدون تأیید سازگاری باید متوقف شود. تا اجرای همان مسیر نصب‌شده با دادهٔ آزمایشی، موفقیت adapterهای قبلی جای این زنجیره نیست.
- **تنظیمات مالک:** fingerprint مستقل، مقصد خصوصی backup خارج VPS و ورودی امن کلیدها و تنظیمات بعداً موردنیازند؛ برای fixture CI از هیچ secret یا مقصد واقعی استفاده نشده است. ثبت مقصد و هر تصمیم قراردادی لازم در Vault جداگانه پیگیری می‌شود؛ Vault در این نشست تغییر نکرد.
