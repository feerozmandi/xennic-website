'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { alternateHref, getDictionary, LOCALES, type Locale } from '@/lib/i18n'

/**
 * Language switch, drawn with the same liquid-glass language as the theme
 * switch. Both editions are live, so the inactive language is a link to the same
 * page in the other language; `hreflang` is set so browsers and crawlers do not
 * mistake the twin page for a duplicate.
 */
export function LocaleSwitch({ locale, compact = false }: { locale: Locale; compact?: boolean }) {
  const pathname = usePathname() ?? (locale === 'en' ? '/en' : '/')
  const dict = getDictionary(locale)

  return (
    <div className={`locale-switch${compact ? ' locale-switch--compact' : ''}`}>
      <ul className="locale-switch__list" aria-label={dict.localeSwitch.help}>
        {LOCALES.map((code) => {
          const isActive = code === locale
          const label = dict.localeSwitch[code]
          const short = code === 'fa' ? 'فا' : 'EN'
          const dir = code === 'fa' ? 'rtl' : 'ltr'
          return (
            <li key={code}>
              {isActive ? (
                <span className="locale-switch__option is-active" lang={code} dir={dir} aria-current="true">
                  {short}
                  <span className="sr-only"> — {label}</span>
                </span>
              ) : (
                <Link
                  href={alternateHref(pathname, code)}
                  hrefLang={code}
                  lang={code}
                  dir={dir}
                  className="locale-switch__option"
                >
                  {short}
                  <span className="sr-only"> — {label}</span>
                </Link>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
