/**
 * The three hero slides.
 *
 * Every word here is drawn from copy that was already approved (L2-MKT-004 and
 * its reviewed English translation): the company slogan, the distribution
 * supervision service and the "smart engineering" principle. Nothing new is
 * claimed, and each slide names the field of work rather than a project.
 *
 * The artwork is generated illustration, not a photograph of a Xennic project,
 * so each slide states that in its own caption — the same rule the rest of the
 * site follows.
 */
import type { Locale } from './i18n'

export type HeroSlide = {
  id: string
  image: { src: string; width: number; height: number }
  eyebrow: string
  title: string
  summary: string
  primary: { href: string; label: string }
  secondary: { href: string; label: string }
  /** Shown under the slide: what the picture is, and what it is not. */
  caption: string
}

const ART = {
  distribution: { src: '/images/hero-distribution.webp', width: 1600, height: 900 },
  renewables: { src: '/images/hero-renewables.webp', width: 1600, height: 900 },
  smartGrid: { src: '/images/hero-smart-grid.webp', width: 1600, height: 900 },
} as const

const COPY: Record<Locale, Omit<HeroSlide, 'id' | 'image'>[]> = {
  fa: [
    {
      eyebrow: 'مهندسی برق، انرژی و اتوماسیون',
      title: 'مهندسی انرژی برای تصمیم‌های دقیق‌تر و آینده‌ای هوشمندتر',
      summary:
        'زر نور نیرو یکتا در حوزهٔ مهندسی برق، انرژی و انرژی‌های تجدیدپذیر، راهکارهای مهندسی، مشاوره و تحلیل تخصصی ارائه می‌دهد؛ با تکیه بر دانش مهندسی و فناوری‌های نوین.',
      primary: { href: '/contact', label: 'درخواست مشاورهٔ مهندسی' },
      secondary: { href: '/services', label: 'آشنایی با خدمات' },
      caption: 'تصویر شاخص از شبکهٔ توزیع برق؛ عکس پروژهٔ مشخصی نیست.',
    },
    {
      eyebrow: 'شبکهٔ توزیع برق',
      title: 'نظارت فنی بر پروژه‌های شبکهٔ توزیع',
      summary: 'نظارت فنی بر پروژه‌های شبکهٔ توزیع هوایی، زمینی و پست؛ از فشار متوسط تا تحویل نهایی.',
      primary: { href: '/services/distribution-supervision', label: 'جزئیات نظارت بر توزیع' },
      secondary: { href: '/track-record', label: 'پیشینهٔ کاری' },
      caption: 'تصویر شاخص از شبکهٔ توزیع؛ عکس پروژهٔ مشخصی نیست.',
    },
    {
      eyebrow: 'مهندسی هوشمند',
      title: 'تلفیق دانش مهندسی با فناوری و هوش مصنوعی',
      summary: 'راهکارهای مشاوره، طراحی و نظارت با تکیه بر ابزارهای دیجیتال و تحلیل داده‌محور مصرف انرژی.',
      primary: { href: '/services', label: 'مرور حوزه‌های خدمات' },
      secondary: { href: '/contact', label: 'گفت‌وگو دربارهٔ پروژه' },
      caption: 'تصویر شاخص از هوشمندسازی شبکه؛ عکس پروژهٔ مشخصی نیست.',
    },
  ],
  en: [
    {
      eyebrow: 'Electrical, energy and automation engineering',
      title: 'Energy engineering for sharper decisions and a smarter future',
      summary:
        'Zar-e Noor-e Niroo-e Yekta works in electrical engineering, energy and renewable energy, offering engineering solutions, consultancy and specialist analysis, built on engineering knowledge and modern technology.',
      primary: { href: '/en/contact', label: 'Request engineering advice' },
      secondary: { href: '/en/services', label: 'Explore our services' },
      caption: 'Illustrative image of a distribution network; it is not a photograph of a specific project.',
    },
    {
      eyebrow: 'Distribution networks',
      title: 'Technical supervision of distribution projects',
      summary: 'Technical supervision of overhead, underground and substation distribution projects, from medium voltage to final handover.',
      primary: { href: '/en/services/distribution-supervision', label: 'Distribution supervision details' },
      secondary: { href: '/en/track-record', label: 'Track record' },
      caption: 'Illustrative image of a distribution network; it is not a photograph of a specific project.',
    },
    {
      eyebrow: 'Smart engineering',
      title: 'Engineering knowledge combined with technology and artificial intelligence',
      summary: 'Consultancy, design and supervision supported by digital tools and data-driven analysis of energy use.',
      primary: { href: '/en/services', label: 'Browse the service areas' },
      secondary: { href: '/en/contact', label: 'Talk about your project' },
      caption: 'Illustrative image of grid automation; it is not a photograph of a specific project.',
    },
  ],
}

const IMAGES = [ART.distribution, ART.renewables, ART.smartGrid] as const
const IDS = ['distribution', 'renewables', 'smart-grid'] as const

export function heroSlides(locale: Locale): HeroSlide[] {
  return COPY[locale].map((slide, index) => ({ ...slide, id: IDS[index], image: IMAGES[index] }))
}
