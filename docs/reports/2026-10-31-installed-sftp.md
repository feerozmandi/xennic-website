# ادامهٔ helper نصب‌شده و انتقال SFTP

- **تاریخ:** ۲۰۲۶-۱۰-۳۱؛ [PR #13](https://github.com/feerozmandi/xennic-website/pull/13). هیچ SSH عملیاتی، استقرار، تغییر VPS یا DNS انجام نشده است.
- **نتیجه:** انتقال SFTP با کد و مسیرهای ثابت و نصب‌کنندهٔ محدود اضافه شد؛ این تنها بخشی از زنجیره است و هنوز به `backup-verify` کنترل‌کننده وصل نیست. installer فقط helper انتقال و وابستگی‌های آن را نصب می‌کند، نه مجموعهٔ کامل helperهای استقرار، sudoers یا SSH.

## تغییرات

- journal پیش از backup و هر maintenance احتمالی blocked می‌شود. شکست backup، عملیات بعدی را متوقف و وضعیت blocked را حفظ می‌کند؛ blocked به‌تنهایی به معنای توقف نویسنده‌ها نیست. توقف واقعی app، snapshot و wiring عملیاتی هنوز وجود ندارد.
- `scripts/preview-backup-sftp.py` فقط manifest محدود را از stdin می‌گیرد؛ ورودی دلخواه برای مسیر، host، argv یا محیط نمی‌پذیرد. پیکربندی root-owned شامل نام کاربر و پورت تأییدشده، مسیر ثابت SSH key و known_hosts، `StrictHostKeyChecking=yes` و SFTP batch بدون shell است. فایل age ثابت upload و مجدداً download و hash آن مقایسه می‌شود؛ رکورد hash در state root-owned ذخیره می‌شود. این رکورد امضای خارجی یا اثبات مقصد خارج VPS نیست و جای restore مستقل را نمی‌گیرد.
- `scripts/install-preview-sftp-helper.py` فقط staging ثابت و root-owned `/root/xennic-preview-install` را می‌خواند، ورودی ندارد، نصب موجود را بازنویسی نمی‌کند و فایل‌ها را root-only در `/usr/local/libexec/xennic-preview` قرار می‌دهد. تا تکمیل installer کلی این مسیر برای نصب استقرار کامل نیست.
- job جدید `installed-sftp` در runner دورریختنی GitHub یک SSH/SFTP server مستقل با کلید آزمایشی اجرا می‌کند، فایل‌ها را ابتدا root-owned stage و helper واقعی را نصب می‌کند، سپس upload/readback و شکست اتصال و حفاظت فایل/blocked را کنترل می‌کند. منبع release و داده مصنوعی است؛ این job آزمون کل backend، توقف نویسنده، مهاجرت، GHCR یا restore نیست. انتشار در dev وابسته به موفقیت این job نیز شد.
- آزمون‌های Python transaction، backend و readiness محلی موفق شدند؛ Docker و SSH عملیاتی در Arena اجرا نشدند. نتیجهٔ job جدید در CI همین PR پیگیری می‌شود.

## مانع‌ها و راه‌حل بعدی

- **کد:** `backup-verify` باید سرویس app و همهٔ writerهای وابسته را واقعاً متوقف، PostgreSQL را فعال و dump/media را با age بسته‌بندی و سپس همین SFTP helper را فراخوانی کند؛ اجرای restore مستقل پیش از migration و حالت امن توقف/بازیابی در خطا لازم است. صرف انتقال ciphertext یا blocked کافی نیست.
- **کد:** helperهای release-check/current/pull/migrate/activate/health/rollback و installer یکپارچه هنوز آماده نیستند. verifier باید به run موفق و artifact همان commit متصل شود؛ مهاجرت ناشناخته یا بدون تأیید سازگاری باید متوقف شود. تا اجرای همان مسیر نصب‌شده با دادهٔ آزمایشی، موفقیت adapterهای قبلی جای این زنجیره نیست.
- **تنظیمات مالک:** fingerprint مستقل، مقصد خصوصی backup خارج VPS و ورودی امن کلیدها و تنظیمات بعداً موردنیازند؛ برای fixture CI از هیچ secret یا مقصد واقعی استفاده نشده است. ثبت مقصد و هر تصمیم قراردادی لازم در Vault جداگانه پیگیری می‌شود؛ Vault در این نشست تغییر نکرد.
