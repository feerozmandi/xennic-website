/**
 * Locale registry and interface strings.
 *
 * Persian is the source language and English is a translation of the approved
 * Persian copy — never an independent rewrite. The dictionary below covers
 * everything the interface says in its own voice (labels, buttons, notices,
 * validation messages); page bodies come from `content.ts` (Persian, from the
 * CMS) or from `i18n-content.ts` (the English translation).
 *
 * This module is pure data: it is safe to import from server components and
 * from client components.
 */
export type Locale = 'fa' | 'en'

export const LOCALES: Locale[] = ['fa', 'en']
export const DEFAULT_LOCALE: Locale = 'fa'

export type Dictionary = typeof fa

const fa = {
  htmlLang: 'fa',
  dir: 'rtl',
  skipToContent: 'رفتن به محتوای اصلی',
  logoHome: 'Xennic — زر نور نیرو یکتا، صفحهٔ اصلی',
  brandSub: 'زر نور نیرو یکتا',
  opensInNewTab: 'در پنجرهٔ تازه باز می‌شود',
  comingSoon: 'به‌زودی',
  notPublishedBadge: 'در حال آماده‌سازی',
  notPublishedTitle: 'این صفحه هنوز منتشر نشده است',
  notPublishedBody: (title: string) =>
    `محتوای «${title}» پس از تأیید منتشر می‌شود؛ تا آن زمان برای هر پرسش از مسیرهای تماس استفاده کنید.`,
  contactRoutes: 'مسیرهای تماس',
  home: 'خانه',
  nav: {
    label: 'ناوبری اصلی',
    mobileLabel: 'ناوبری موبایل',
    menuLabel: 'منوی اصلی',
    open: 'باز کردن منو',
    close: 'بستن منو',
    cta: 'درخواست مشاوره',
    ctaShort: 'درخواست مشاوره',
    brandTagline: 'زر نور نیرو یکتا | Xennic — مهندسی برق، انرژی و اتوماسیون',
  },
  theme: {
    toLight: 'حالت شب فعال است؛ تغییر به حالت روز',
    toDark: 'حالت روز فعال است؛ تغییر به حالت شب',
    lightOn: 'حالت روز روشن شد',
    darkOn: 'حالت شب روشن شد',
  },
  localeSwitch: {
    help: 'زبان سایت',
    fa: 'فارسی',
    en: 'English',
  },
  footer: {
    note: 'زر نور نیرو یکتا (برند تجاری: Xennic) — مهندسی برق قدرت، انرژی و اتوماسیون؛ مشاوره، طراحی، نظارت و آموزش تخصصی.',
    // Two further lines, both derived from approved copy: the six service areas
    // and the standards already named on the service pages. No new claim.
    about: [
      'شش حوزهٔ تخصصی: مشاورهٔ برق صنعتی، طراحی تأسیسات برق ساختمان، نظارت بر پروژه‌های توزیع، ممیزی انرژی، ارت و صاعقه‌گیر، و آموزش فنی.',
      'تحلیل و طراحی هم‌سو با مبحث ۱۳ مقررات ملی ساختمان و استانداردهای IEC، با تکیه بر دانش مهندسی و ابزارهای دیجیتال.',
    ],
    quickLinks: 'دسترسی سریع',
    services: 'خدمات',
    information: 'اطلاعات',
    footerNav: 'ناوبری فوتر',
    servicesNav: 'خدمات در فوتر',
    legalNav: 'صفحات حقوقی',
    // Heading of the fourth footer column: the confirmed contact channels and
    // the three confirmed social channels, nothing else.
    contact: 'اطلاعات تماس',
    // Heading of the contact column and the link that opens the contact page
    // are two different things, so they get two different labels.
    contactPage: 'تماس با ما',
    socialsLabel: 'پیام‌رسان‌ها و شبکه‌های اجتماعی',
    copyright: 'زر نور نیرو یکتا | Xennic',
    disclaimer: 'محتوای این نسخه صرفاً از منابع تأییدشدهٔ سازمان منتشر می‌شود.',
  },
  legal: { privacy: 'حریم خصوصی', terms: 'شرایط استفاده', cookies: 'کوکی‌ها' },
  hero: {
    note: 'اطلاعات تماس رسمی فقط پس از تأیید سازمان منتشر می‌شود؛ تا آن زمان درخواست‌ها از صفحهٔ تماس پیگیری می‌شوند.',
    factsLabel: 'نگاه کلی در یک نگاه',
    carouselLabel: 'معرفی شرکت در سه پرده',
    previous: 'پردهٔ پیشین',
    next: 'پردهٔ بعدی',
    pause: 'توقف پخش خودکار',
    play: 'شروع پخش خودکار',
    slideOf: (index: number, total: number) => `پردهٔ ${index} از ${total}`,
    slideChange: (index: number, total: number, title: string) => `پردهٔ ${index} از ${total}: ${title}`,
    goTo: (index: number) => `رفتن به پردهٔ ${index}`,
  },
  principles: {
    eyebrow: 'اصول کاری',
    title: 'چرا Xennic',
    lead: 'پنج اصلی که چارچوب تصمیم‌گیری مهندسی ما را شکل می‌دهند.',
  },
  servicesSection: {
    eyebrow: 'خدمات',
    title: 'از مشاورهٔ فنی تا نظارت و آموزش',
    lead: 'خدمات در حوزهٔ برق قدرت، تأسیسات، انرژی و آموزش تخصصی؛ هر خدمت با دامنهٔ مشخص و خروجی قابل استناد.',
    all: 'همهٔ خدمات و دوره‌ها',
    more: 'جزئیات خدمت',
    imageNote: 'تصاویر، شاخص حوزهٔ کار هستند و به پروژه یا کارفرمای مشخصی اشاره ندارند.',
  },
  founder: {
    eyebrow: 'پیشینهٔ مؤسس',
    readRecord: 'مطالعهٔ پیشینهٔ حرفه‌ای',
    asideLabel: 'مشخصات مؤسس',
    role: 'مؤسس',
  },
  platform: {
    status: 'این بخش پیش‌نمایش طراحی است؛ هیچ قابلیت یا دسترسی جدیدی در سایت فعال نشده است.',
  },
  content: {
    aboutEyebrow: 'دربارهٔ شرکت',
    aboutAsideTitle: 'تیم و مؤسس',
    aboutAsideText: 'معرفی مؤسس و سابقهٔ حرفه‌ای ایشان، جدا از سابقهٔ شرکت.',
    team: 'تیم',
    record: 'پیشینهٔ مهندسی',
    services: 'خدمات',
    servicesEyebrow: 'دامنهٔ خدمات',
    servicesLead: 'خدمات در حوزهٔ برق قدرت، تأسیسات، انرژی و آموزش تخصصی؛ هر خدمت با دامنهٔ مشخص و خروجی قابل استناد.',
    recordEyebrow: 'پیشینهٔ مؤسس',
    recordTitle: 'تجربه و پیشینهٔ مهندسی',
    recordLead: 'تجربهٔ عملی مؤسس Xennic در شبکهٔ توزیع و پروژه‌های برق، پیش از تأسیس این مجموعه.',
    recordBadge: 'پیش از تأسیس Xennic',
    recordNote: 'این پیشینه، سابقهٔ حرفه‌ای مؤسس پیش از تأسیس Xennic است و به‌معنای سابقهٔ پروژه‌های شرکت نیست.',
    teamEyebrow: 'افراد',
    teamTitle: 'تیم',
    teamLead: 'معرفی مؤسس و سابقهٔ حرفه‌ای ایشان؛ سابقهٔ پروژه‌های شرکت در بخش پیشینهٔ مهندسی آمده است.',
    teamRecordLink: 'پیشینهٔ حرفه‌ای',
    serviceEyebrow: 'خدمت',
    serviceAsideTitle: 'گفت‌وگو دربارهٔ این خدمت',
    serviceAsideText: 'برای بررسی دامنهٔ کار و زمان‌بندی، از مسیرهای تماس استفاده کنید یا فرم درخواست را پر کنید.',
    serviceSoonText: 'این خدمت هنوز برای درخواست باز نشده است.',
    allServices: 'همهٔ خدمات',
    defaultCta: 'درخواست مشاوره',
  },
  contactPage: {
    eyebrow: 'مسیرهای تماس',
    title: 'تماس با Xennic',
    lead: 'برای گفت‌وگو دربارهٔ پروژه، درخواست مشاورهٔ فنی یا پیگیری یک موضوع، از هر یک از مسیرهای زیر استفاده کنید. همین اطلاعات در پایین همهٔ صفحه‌ها هم آمده است.',
    direct: 'تماس مستقیم',
    social: 'پیام‌رسان‌ها و شبکه‌های اجتماعی',
    founder: 'دربارهٔ مؤسس',
    founderLink: 'پیشینهٔ حرفه‌ای مؤسس',
  },
  breadcrumb: 'مسیر صفحه',
  placeholderBody: 'ساختار اولیهٔ صفحه؛ محتوا پس از تأیید ساختار افزوده می‌شود.',
  more: 'دسترسی بیشتر',
  actions: 'اقدام',
  teamEmpty: 'معرفی اعضای تیم پس از تأیید منتشر می‌شود.',
  methods: {
    phone: 'تلفن همراه',
    phoneHint: 'تماس مستقیم با مؤسس',
    emailInfo: 'رایانامهٔ رسمی',
    emailFounder: 'رایانامهٔ مؤسس',
    bale: 'بله',
    telegram: 'تلگرام',
    instagram: 'اینستاگرام',
  },
  formErrors: {
    nameShort: 'نام را کامل‌تر وارد کنید.',
    nameLong: 'نام بیش از حد بلند است.',
    phoneLong: 'شمارهٔ تماس بیش از حد بلند است.',
    emailLong: 'رایانامهٔ بیش از حد بلند است.',
    subjectLong: 'موضوع بیش از حد بلند است.',
    messageShort: 'متن پیام را کامل‌تر بنویسید (حداقل ۱۰ نویسه).',
    messageLong: 'متن پیام بیش از حد بلند است.',
    emailFormat: 'قالب رایانامه درست نیست.',
    phoneFormat: 'شمارهٔ تماس فقط می‌تواند رقم و علامت‌های رایج داشته باشد.',
    contactRequired: 'برای پاسخ، شمارهٔ تماس یا رایانامه را وارد کنید.',
    invalid: 'درخواست نامعتبر است و ثبت نشد.',
    fixFields: 'برخی از فیلدها نیاز به اصلاح دارند.',
    rateLimited: 'تعداد پیام‌های ارسالی از این نشانی زیاد بوده است؛ چند دقیقه بعد دوباره تلاش کنید.',
    storeFailed: 'ثبت پیام در سامانه انجام نشد. لطفاً از تلفن یا رایانامهٔ رسمی استفاده کنید.',
    success: 'پیام شما در سامانهٔ Xennic ثبت شد. برای پاسخ سریع‌تر می‌توانید تلفنی هم تماس بگیرید.',
    defaultSubject: 'درخواست تماس از وب‌سایت',
  },

  form: {
    title: 'فرم درخواست تماس',
    note: 'پیام شما در سامانهٔ داخلی Xennic ثبت می‌شود. برای پاسخ سریع‌تر، شمارهٔ تماس یا رایانامه را وارد کنید.',
    name: 'نام و نام خانوادگی',
    phone: 'شمارهٔ تماس',
    email: 'رایانامه',
    subject: 'موضوع',
    message: 'متن پیام',
    optional: '(اختیاری)',
    required: 'الزامی',
    submit: 'ارسال پیام',
    company: 'شرکت',
    requiredNote: 'برای ارسال، هر دو فیلد ستاره‌دار الزامی است.',
    sending: 'در حال ارسال…',
    successTitle: 'پیام ثبت شد',
    successHint: 'اگر پاسخ فوری لازم دارید، از شمارهٔ تلفن یا پیام‌رسان‌های همین صفحه استفاده کنید.',
    failureTitle: 'پیام ثبت نشد',
  },
}

const en: Dictionary = {
  htmlLang: 'en',
  dir: 'ltr',
  skipToContent: 'Skip to main content',
  logoHome: 'Xennic — Zar-e Noor-e Niroo-e Yekta, home page',
  brandSub: 'Zar-e Noor-e Niroo-e Yekta',
  opensInNewTab: 'opens in a new tab',
  comingSoon: 'Coming soon',
  notPublishedBadge: 'In preparation',
  notPublishedTitle: 'This page has not been published yet',
  notPublishedBody: (title: string) =>
    `The “${title}” content is published once it is approved. Until then, please use the contact channels for any question.`,
  contactRoutes: 'Contact',
  home: 'Home',
  nav: {
    label: 'Primary navigation',
    mobileLabel: 'Mobile navigation',
    menuLabel: 'Main menu',
    open: 'Open menu',
    close: 'Close menu',
    cta: 'Request a consultation',
    ctaShort: 'Consultation',
    brandTagline: 'Zar-e Noor-e Niroo-e Yekta | Xennic — electrical, energy and automation engineering',
  },
  theme: {
    toLight: 'Dark mode is on; switch to light mode',
    toDark: 'Light mode is on; switch to dark mode',
    lightOn: 'Light mode enabled',
    darkOn: 'Dark mode enabled',
  },
  localeSwitch: {
    help: 'Site language',
    fa: 'فارسی',
    en: 'English',
  },
  footer: {
    note: 'Zar-e Noor-e Niroo-e Yekta (trade name: Xennic) — power, energy and automation engineering; consultancy, design, supervision and specialist training.',
    about: [
      'Six specialist areas: industrial electrical consulting, building electrical design, distribution project supervision, energy auditing, earthing and lightning protection, and technical training.',
      'Analysis and design aligned with Chapter 13 of the national building code and IEC standards, drawing on engineering knowledge and digital tools.',
    ],
    quickLinks: 'Quick links',
    services: 'Services',
    information: 'Information',
    footerNav: 'Footer navigation',
    servicesNav: 'Services in the footer',
    legalNav: 'Legal pages',
    contact: 'Contact information',
    contactPage: 'Contact us',
    socialsLabel: 'Messengers and social networks',
    copyright: 'Zar-e Noor-e Niroo-e Yekta | Xennic',
    disclaimer: 'Every statement on this site comes from approved organisational sources.',
  },
  legal: { privacy: 'Privacy', terms: 'Terms of use', cookies: 'Cookies' },
  hero: {
    note: 'The approved contact channels are published on the contact page, where you can also send a request.',
    factsLabel: 'Overview at a glance',
    carouselLabel: 'The company in three slides',
    previous: 'Previous slide',
    next: 'Next slide',
    pause: 'Pause the automatic slideshow',
    play: 'Start the automatic slideshow',
    slideOf: (index: number, total: number) => `Slide ${index} of ${total}`,
    slideChange: (index: number, total: number, title: string) => `Slide ${index} of ${total}: ${title}`,
    goTo: (index: number) => `Go to slide ${index}`,
  },
  principles: {
    eyebrow: 'How we work',
    title: 'Why Xennic',
    lead: 'Five principles that shape how we make engineering decisions.',
  },
  servicesSection: {
    eyebrow: 'Services',
    title: 'From technical consulting to supervision and training',
    lead: 'Work across power engineering, building services, energy and specialist training — each service with a defined scope and a traceable output.',
    all: 'All services and courses',
    more: 'Service details',
    imageNote: 'The images illustrate the field of work; they do not show a specific project or client.',
  },
  founder: {
    eyebrow: 'Founder’s record',
    readRecord: 'Read the professional record',
    asideLabel: 'Founder details',
    role: 'Founder',
  },
  platform: {
    status: 'This section is a design preview; no new capability or access has been enabled on the site.',
  },
  content: {
    aboutEyebrow: 'About the company',
    aboutAsideTitle: 'Team and founder',
    aboutAsideText: 'The founder’s introduction and professional record, kept separate from the company’s own record.',
    team: 'Team',
    record: 'Track record',
    services: 'Services',
    servicesEyebrow: 'Scope of services',
    servicesLead: 'Work across power engineering, building services, energy and specialist training — each service with a defined scope and a traceable output.',
    recordEyebrow: 'Founder’s record',
    recordTitle: 'Engineering experience and track record',
    recordLead: 'The professional experience of Xennic’s founder in distribution networks and electrical projects, before this company was established.',
    recordBadge: 'Before Xennic was founded',
    recordNote: 'This is the founder’s professional record before Xennic existed; it is not a record of company projects.',
    teamEyebrow: 'People',
    teamTitle: 'Team',
    teamLead: 'The founder and his professional record; the company’s project record is on the track-record page.',
    teamRecordLink: 'Professional record',
    serviceEyebrow: 'Service',
    serviceAsideTitle: 'Discuss this service',
    serviceAsideText: 'To review scope and timing, use the contact channels or fill in the request form.',
    serviceSoonText: 'This service is not open for requests yet.',
    allServices: 'All services',
    defaultCta: 'Request a consultation',
  },
  contactPage: {
    eyebrow: 'Contact channels',
    title: 'Contact Xennic',
    lead: 'To discuss a project, request technical advice or follow up an open topic, use any of the channels below. The same details appear at the bottom of every page.',
    direct: 'Direct contact',
    social: 'Messengers and social networks',
    founder: 'About the founder',
    founderLink: 'Founder’s professional record',
  },
  breadcrumb: 'Breadcrumb',
  placeholderBody: 'Page skeleton; the content is added once the structure is approved.',
  more: 'More from Xennic',
  actions: 'Next step',
  teamEmpty: 'Team members are published once their introductions are approved.',
  methods: {
    phone: 'Mobile phone',
    phoneHint: 'Direct line to the founder',
    emailInfo: 'Official email',
    emailFounder: 'Founder’s email',
    bale: 'Bale',
    telegram: 'Telegram',
    instagram: 'Instagram',
  },
  formErrors: {
    nameShort: 'Please enter your full name.',
    nameLong: 'The name is too long.',
    phoneLong: 'The phone number is too long.',
    emailLong: 'The email address is too long.',
    subjectLong: 'The subject is too long.',
    messageShort: 'Please write a little more (at least 10 characters).',
    messageLong: 'The message is too long.',
    emailFormat: 'That email address does not look valid.',
    phoneFormat: 'A phone number may only contain digits and common punctuation.',
    contactRequired: 'Add a phone number or an email address so we can reply.',
    invalid: 'The request was not valid and was not stored.',
    fixFields: 'Some fields need attention.',
    rateLimited: 'Too many messages have been sent from this address; please try again in a few minutes.',
    storeFailed: 'The message could not be stored. Please use the official phone number or email address instead.',
    success: 'Your message is stored in Xennic’s system. If you would like a faster reply, you can also call us.',
    defaultSubject: 'Website contact request',
  },

  form: {
    title: 'Contact request form',
    note: 'Your message is stored in Xennic’s internal system. Add a phone number or an email address if you would like a faster reply.',
    name: 'Full name',
    phone: 'Phone number',
    email: 'Email address',
    subject: 'Subject',
    message: 'Message',
    optional: '(optional)',
    required: 'required',
    submit: 'Send request',
    company: 'Company',
    requiredNote: 'Both fields marked with a star are required to send.',
    sending: 'Sending…',
    successTitle: 'Message received',
    successHint: 'If you need a quick answer, call the phone number or use one of the messengers on this page.',
    failureTitle: 'The message was not stored',
  },
}

const dictionaries: Record<Locale, Dictionary> = { fa, en }

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale]
}

export function isLocale(value: string | undefined): value is Locale {
  return value === 'fa' || value === 'en'
}

/** Prefix a Persian path for the requested locale: `/contact` → `/en/contact`. */
export function localeHref(locale: Locale, path: string): string {
  if (locale === 'fa') return path
  if (path === '/') return '/en'
  return `/en${path}`
}

export function isEnglishPath(pathname: string): boolean {
  return pathname === '/en' || pathname.startsWith('/en/')
}

/** The same page in the other language, used by the language switch. */
export function alternateHref(pathname: string, target: Locale): string {
  const base = isEnglishPath(pathname) ? (pathname === '/en' ? '/' : pathname.slice(3)) : pathname
  return localeHref(target, base || '/')
}
