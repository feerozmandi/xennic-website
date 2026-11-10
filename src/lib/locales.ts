/**
 * Locale registry for the public site.
 *
 * The product documentation targets a bilingual site (Persian first, English
 * second). Routing, translated copy and SEO alternates for the English tree are
 * not approved yet, so `en` is registered as disabled: the control renders the
 * real design and says so instead of navigating to a page that does not exist.
 * Enabling it is a single flag once `/en` content is approved.
 */
export type LocaleCode = 'fa' | 'en'

export type Locale = {
  code: LocaleCode
  short: string
  label: string
  dir: 'rtl' | 'ltr'
  enabled: boolean
  /** Where the switch points once the locale is enabled. */
  href: string
}

export const LOCALES: Locale[] = [
  { code: 'fa', short: 'فا', label: 'فارسی', dir: 'rtl', enabled: true, href: '/' },
  { code: 'en', short: 'EN', label: 'English', dir: 'ltr', enabled: false, href: '/en' },
]

export const ACTIVE_LOCALE: LocaleCode = 'fa'
