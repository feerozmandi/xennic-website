import Link from 'next/link'
import { ACTIVE_LOCALE, LOCALES } from '@/lib/locales'

/**
 * Language switch, drawn with the same liquid-glass language as the theme
 * switch. The active locale is a plain link; locales whose tree is not live yet
 * are rendered as disabled segments with an explicit note, so the control never
 * promises a page that does not exist.
 */
export function LocaleSwitch({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`locale-switch${compact ? ' locale-switch--compact' : ''}`}>
      <span className="sr-only" id="locale-switch-help">
        زبان سایت. نسخهٔ انگلیسی در حال آماده‌سازی است.
      </span>
      <ul className="locale-switch__list" aria-describedby="locale-switch-help">
        {LOCALES.map((locale) => {
          const isActive = locale.code === ACTIVE_LOCALE
          return (
            <li key={locale.code}>
              {locale.enabled ? (
                <Link
                  href={locale.href}
                  lang={locale.code}
                  dir={locale.dir}
                  aria-current={isActive ? 'true' : undefined}
                  className={`locale-switch__option${isActive ? ' is-active' : ''}`}
                >
                  {locale.short}
                  <span className="sr-only"> — {locale.label}</span>
                </Link>
              ) : (
                <span
                  className="locale-switch__option is-disabled"
                  lang={locale.code}
                  dir={locale.dir}
                  aria-disabled="true"
                  title={`${locale.label} — در حال آماده‌سازی`}
                >
                  {locale.short}
                  <span className="locale-switch__badge">به‌زودی</span>
                  <span className="sr-only"> — {locale.label}، در حال آماده‌سازی</span>
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
