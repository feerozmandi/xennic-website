# معماری وب‌سایت Xennic

این سند مرزهای چهار لایهٔ سایت را تعریف می‌کند و می‌گوید هر مرز با چه ابزاری **اجبار** می‌شود. مرجع معماری کلان، سند `META-INT-150` در Vault است؛ این سند فقط پیاده‌سازی همین مخزن را توصیف می‌کند و تصمیم تازه نمی‌سازد.

## لایه‌ها

| لایه | مسیر | چه چیزی دارد | چه چیزی ندارد |
|---|---|---|---|
| **UI** | `src/components/**` | کامپوننت‌های نمایشی، بدون دانش از CMS | فراخوانی Payload، خواندن محیط، منطق داده |
| **tokens** | `src/app/(frontend)/styles.css` | رنگ، فاصله، شیشه، حرکت — تنها منبع ظاهر | مقدار سخت‌کدشده در کامپوننت |
| **content** | `src/lib/*.ts` (به‌جز دو استثنای زیر) | متن تأییدشده، مدل‌های نمایش، توکن‌های TS | دسترسی به پایگاه‌داده |
| **server** | `src/lib/content.ts`، `src/lib/contact-actions.ts`، `src/collections/**`، `src/payload.config.ts` | پرس‌وجوی Payload، Server Action، مجموعه‌ها | رنگ، چیدمان، JSX صفحه |
| **app** | `src/app/(frontend)/**` | ترکیب: داده را از server می‌گیرد، به UI می‌دهد | منطق نمایشی تکراری |

دو استثنای اعلام‌شده در `src/lib`: `content.ts` (تنها جای خواندن محتوا) و `contact-actions.ts` (Server Action فرم تماس). هر ماژول دیگری در `src/lib` باید خالص و قابل ایمپورت از هر دو طرف باشد.

## قرارداد داده

جریان داده یک‌طرفه است:

```
Payload document  →  src/lib/content.ts (نقشه‌برداری)  →  view model  →  page  →  component
   (payload-types)          contracts.ts                     props
```

| مدل در `src/lib/contracts.ts` | مصرف‌کننده | منبع |
|---|---|---|
| `ServiceCardModel` | `ServiceCards`، صفحهٔ اصلی | مجموعهٔ `services` |
| `ServiceDetailModel` | صفحهٔ جزئیات خدمت | مجموعهٔ `services` |
| `TrackRecordItemModel` | `TrackRecordList` | مجموعهٔ `track-record-items` |
| `TeamMemberModel` | صفحهٔ تیم | مجموعهٔ `team-members` |
| `RichTextDocument` | `DocumentContent` | فیلد `content` هر دو مجموعه |
| `HomeContent` (`home-content.ts`) | بخش‌های صفحهٔ اصلی | ترکیب `pages` + `services` |

`src/payload-types.ts` تولیدشده است و می‌تواند هر زمان با تغییر schema عوض شود. فقط `contracts.ts` و `content.ts` اجازهٔ وابستگی به آن را دارند؛ کامپوننت‌ها هرگز یک سند Payload نمی‌بینند. نتیجه: تغییر schema در یک تابع نقشه‌برداری حس می‌شود، نه در ده کامپوننت.

## قواعد اجراشدنی

`npm run check:boundaries` این پنج قاعده را روی همهٔ ماژول‌های `src` بررسی می‌کند و با کد غیرصفر خارج می‌شود:

1. ماژول `'use client'` نباید کد سرور را وارد باندل کند (Payload، درایور پایگاه‌داده، دروازهٔ پیش‌نمایش). تنها استثنا `@/lib/contact-actions` است که Server Action است و Next آن را به فراخوانی RPC تبدیل می‌کند.
2. `src/components/**` نباید `@/lib/content` را ایمپورت کند؛ داده به‌صورت props می‌آید.
3. Payload و درایور پایگاه‌داده فقط از `src/app`، `src/collections`، `scripts` و دو ماژول مرزی مجازند.
4. کامپوننت‌های `src/components/ui` فقط توکن‌های خالص (`theme`، `locales`، `navigation`) را می‌خوانند.
5. هیچ کامپوننتی `@/payload-types` را ایمپورت نمی‌کند.

قاعدهٔ ۵ با بازآرایی همین نشست ممکن شد: پیش از آن، `components/content.tsx` مستقیماً تایپ سند Payload را می‌گرفت.

## رازها

- مقادیر محیطی (`DATABASE_URL`، `PAYLOAD_SECRET`، کلید پشتیبان) فقط روی سرور خوانده می‌شوند و هرگز به `NEXT_PUBLIC_*` تبدیل نمی‌شوند.
- `npm run check:bundle` پس از build، همهٔ فایل‌های `.next/static` را می‌خواند و اگر رشتهٔ رازمانند یا **مقدار واقعی** یک متغیر محیطی در آن باشد، build را رد می‌کند.
- `XENNIC_PREVIEW=1` سایت را از ایندکس می‌بندد (`robots.txt` + هدر `X-Robots-Tag`). این یک کنترل SEO است، نه کنترل دسترسی؛ دسترسی با دروازهٔ احراز هویت VPS انجام می‌شود.

## ماژول آیندهٔ پلتفرم

پلتفرم Xennic هنوز ساخته نشده و در سایت فقط یک بخش معرفی با نشان «به‌زودی» دارد. جای اتصال آن از پیش مشخص است: هر منبع داده‌ای که بخواهد در سایت دیده شود باید یکی از مدل‌های `contracts.ts` را تولید کند. بنابراین پلتفرم می‌تواند REST، GraphQL یا جدول تازه باشد، بدون آنکه یک کامپوننت عوض شود. تا زمانی که مدل و منبع تأیید نشده، هیچ کد پلتفرمی در سایت اضافه نمی‌شود.

## اجرا

| فرمان | چه کاری می‌کند |
|---|---|
| `npm run typecheck` | TypeScript |
| `npm run lint` | ESLint |
| `npm run check:boundaries` | پنج قاعدهٔ بالا |
| `npm run build` | ساخت Next |
| `npm run check:bundle` | جست‌وجوی راز در باندل مرورگر (نیازمند build) |
| `npm run verify` | همهٔ موارد بالا به‌جز smoke |

CI در job `checks` سه مورد `typecheck`، `lint`، `check:boundaries` را پیش از build و `check:bundle` را بعد از آن اجرا می‌کند؛ بنابراین نقض مرز و نشت راز، PR را متوقف می‌کند.
