/**
 * Public navigation, shared by the header (client) and footer (server).
 *
 * The `href` values are Persian paths; `navigationFor` prefixes them for the
 * requested locale, so the two language trees can never disagree about where a
 * section lives. Labels are interface copy and come from `i18n.ts`.
 */
import type { Locale } from './i18n'
import { localeHref } from './i18n'

export type NavItem = { href: string; label: string }

const SECTIONS = [
  { path: '/company', fa: 'شرکت', en: 'Company' },
  { path: '/services', fa: 'خدمات', en: 'Services' },
  { path: '/track-record', fa: 'پیشینهٔ مهندسی', en: 'Track record' },
  { path: '/knowledge', fa: 'دانشنامه', en: 'Knowledge' },
  { path: '/platform', fa: 'پلتفرم', en: 'Platform' },
  { path: '/contact', fa: 'تماس', en: 'Contact' },
] as const

export const HOME_LABEL: Record<Locale, string> = { fa: 'خانه', en: 'Home' }

export function navigationFor(locale: Locale): NavItem[] {
  return SECTIONS.map((section) => ({
    href: localeHref(locale, section.path),
    label: section[locale],
  }))
}

/** Persian navigation, kept for modules that are not locale-aware. */
export const navigation: NavItem[] = navigationFor('fa')
