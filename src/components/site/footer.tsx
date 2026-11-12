import Link from 'next/link'
import { Logo } from './logo'
import { getDictionary, localeHref, type Locale } from '../../lib/i18n'
import { en as english } from '../../lib/i18n-content'
import { EMAIL_METHODS, phoneMethod, SOCIAL_METHODS } from '../../lib/contact'
import { CONTACT_ICONS } from '../ui/icons'

const LEGAL = [
  { path: '/privacy', fa: 'حریم خصوصی', en: 'Privacy' },
  { path: '/terms', fa: 'شرایط استفاده', en: 'Terms of use' },
  { path: '/cookies', fa: 'کوکی‌ها', en: 'Cookies' },
] as const

const SERVICE_LINKS = [
  { slug: 'industrial-electrical-consulting', fa: 'مشاورهٔ برق صنعتی' },
  { slug: 'building-electrical-design', fa: 'طراحی برق ساختمان' },
  { slug: 'distribution-supervision', fa: 'نظارت بر توزیع' },
  { slug: 'energy-audit', fa: 'ممیزی انرژی' },
] as const

/**
 * Site footer.
 *
 * Four surfaces: the brand block (official artwork, the about text and the
 * confirmed contact channels), three navigation columns and a final legal bar.
 *
 * Contact rows show a glyph, a small label and the value itself, because a
 * visitor should not have to decode an icon to know what they are calling. The
 * social row is the opposite: the three confirmed channels are icon-only, so
 * each link carries an explicit accessible name and a screen-reader note that
 * it opens in a new tab. Nothing here is hidden behind hover, and every target
 * is at least 44 px so it can be tapped.
 */
export function SiteFooter({ locale = 'fa' }: { locale?: Locale }) {
  const dict = getDictionary(locale)
  const serviceLinks = SERVICE_LINKS.map((link) => ({
    href: localeHref(locale, `/services/${link.slug}`),
    // English titles come from the translated service list, never from a guess.
    label: locale === 'en' ? (english.services.find((s) => s.slug === link.slug)?.title ?? link.slug) : link.fa,
  }))
  const legalLinks = LEGAL.map((item) => ({ href: localeHref(locale, item.path), label: item[locale] }))
  const phone = phoneMethod(locale)
  const methods = dict.methods as Record<string, string>
  const methodLabel = (id: string, fallback: string) => (locale === 'en' ? (methods[id] ?? fallback) : fallback)
  const contactRows = [
    { id: phone.id, label: methods.phone, value: phone.value, href: phone.href },
    ...EMAIL_METHODS.map((method) => ({
      id: method.id,
      label: methods[method.id === 'email-info' ? 'emailInfo' : 'emailFounder'] ?? method.label,
      value: method.value,
      href: method.href,
    })),
  ]

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-grid">
          <nav className="footer-col" aria-label={dict.footer.servicesNav}>
            <h2>{dict.footer.services}</h2>
            <ul>{serviceLinks.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
          </nav>
          <nav className="footer-col" aria-label={dict.footer.legalNav}>
            <h2>{dict.footer.information}</h2>
            <ul>{legalLinks.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
            <ul className="footer-col__extra">
              <li><Link href={localeHref(locale, '/contact')}>{dict.footer.contact}</Link></li>
            </ul>
          </nav>
          <div className="footer-brand">
            <Logo size="sm" locale={locale} />
            <div className="footer-about">
              <p>{dict.footer.note}</p>
              {dict.footer.about.map((line) => <p key={line}>{line}</p>)}
            </div>
            <ul className="footer-contact" aria-label={dict.footer.contact}>
              {contactRows.map((row) => {
                const Icon = CONTACT_ICONS[row.id as keyof typeof CONTACT_ICONS]
                return (
                  <li key={row.id}>
                    <a href={row.href}>
                      <span className="footer-contact__icon" aria-hidden="true"><Icon /></span>
                      <span className="footer-contact__body">
                        <span className="footer-contact__label">{row.label}</span>
                        <span className="footer-contact__value" dir="ltr">{row.value}</span>
                      </span>
                    </a>
                  </li>
                )
              })}
            </ul>
            <ul className="footer-socials" aria-label={dict.footer.socialsLabel}>
              {SOCIAL_METHODS.map((method) => {
                const Icon = CONTACT_ICONS[method.id as keyof typeof CONTACT_ICONS]
                const label = methodLabel(method.id, method.label)
                return (
                  <li key={method.id}>
                    <a
                      href={method.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      // The icon is the only visible content, so the accessible
                      // name also carries the new-tab hint. Name and hint in one
                      // place, no duplicate text for assistive tech to read.
                      aria-label={`${label} — ${dict.opensInNewTab}`}
                    >
                      <Icon />
                    </a>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} {dict.footer.copyright}</span>
          <span>{dict.footer.disclaimer}</span>
        </div>
      </div>
    </footer>
  )
}
