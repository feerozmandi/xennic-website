/**
 * Imagery used across the site, with the words that describe it.
 *
 * Every photograph here is a generated illustration of the field the company
 * works in — distribution networks, substations, panels, earthing, energy
 * measurement and training. None of them is a photograph of a real Xennic
 * project, office, employee or client, so none may be labelled as one: the
 * captions say "illustrative" on purpose, and every screen that shows one also
 * shows that note or a caption that repeats it.
 *
 * Alt text describes what is visible, never what it supposedly proves. Service
 * pages and cards use `alt`, which is deliberately plain; the visible caption
 * (`caption`) carries the "illustrative" qualifier.
 */
import type { Locale } from './i18n'

export type Illustration = {
  src: string
  width: number
  height: number
  alt: Record<Locale, string>
  caption: Record<Locale, string>
}

const CAPTION: Record<Locale, string> = {
  fa: 'تصویر شاخص از حوزهٔ کار؛ عکس پروژهٔ مشخصی نیست.',
  en: 'Illustrative image of the field of work; it is not a photograph of a specific project.',
}

function illustration(
  src: string,
  faAlt: string,
  enAlt: string,
  caption: Partial<Record<Locale, string>> = {},
): Illustration {
  return {
    src,
    width: 1000,
    height: 667,
    alt: { fa: faAlt, en: enAlt },
    caption: { fa: caption.fa ?? CAPTION.fa, en: caption.en ?? CAPTION.en },
  }
}

/** One image per service. Unknown services simply render without a picture. */
export const SERVICE_IMAGES: Record<string, Illustration> = {
  'industrial-electrical-consulting': illustration(
    '/images/field-industrial-panel.webp',
    'ردیف تابلوهای برق فشار ضعیف با کلیدها و کابل‌بندی در اتاق برق صنعتی',
    'A row of low-voltage switchgear cabinets with breakers and wiring in an industrial electrical room',
  ),
  'building-electrical-design': illustration(
    '/images/field-energy-audit.webp',
    'اندازه‌گیری جریان با کلمپ‌متر روی کابل در تابلو برق',
    'Measuring current with a clamp meter on a cable inside a distribution board',
  ),
  'distribution-supervision': illustration(
    '/images/field-distribution-lines.webp',
    'تعمیرات خط هوایی توزیع با بالابر و دو تکنسین روی تیر',
    'Overhead distribution line work from a bucket truck with two technicians at the pole',
  ),
  'energy-audit': illustration(
    '/images/field-substation.webp',
    'ترانس توزیع و تابلوهای کلید در محوطهٔ پست توزیع',
    'A distribution transformer and switchgear cabinets in a distribution substation yard',
  ),
  'grounding-lightning-protection': illustration(
    '/images/field-earthing.webp',
    'هادی مسی و میلهٔ صاعقه‌گیر روی بام ساختمان',
    'Copper down conductor and a lightning rod on a building roof',
  ),
  'technical-training': illustration(
    '/images/field-training.webp',
    'کارگاه آموزش برق با دکل تمرینی و دستکش‌های عایق',
    'An electrical training workshop with a practice pole and insulating gloves',
  ),
}

export function serviceImage(slug: string): Illustration | null {
  return SERVICE_IMAGES[slug] ?? null
}

/** The image used on the track-record page and the company page. */
export const FIELD_IMAGES = {
  distribution: SERVICE_IMAGES['distribution-supervision'],
  substation: SERVICE_IMAGES['energy-audit'],
  panels: SERVICE_IMAGES['industrial-electrical-consulting'],
} as const
