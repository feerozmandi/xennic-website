import Link from 'next/link'
import { Logo } from './logo'
import { getDictionary, localeHref, type Locale } from '../../lib/i18n'
import { en as english } from '../../lib/i18n-content'
import { navigationFor } from '../../lib/navigation'
import { EMAIL_METHODS, phoneMethod, SOCIAL_METHODS } from '../../lib/contact'

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

export function SiteFooter({ locale = 'fa' }: { locale?: Locale }) {
  const dict = getDictionary(locale)
  const nav = navigationFor(locale)
  const serviceLinks = SERVICE_LINKS.map((link) => ({
    href: localeHref(locale, `/services/${link.slug}`),
    // English titles come from the translated service list, never from a guess.
    label: locale === 'en' ? (english.services.find((s) => s.slug === link.slug)?.title ?? link.slug) : link.fa,
  }))
  const legalLinks = LEGAL.map((item) => ({ href: localeHref(locale, item.path), label: item[locale] }))
  const phone = phoneMethod(locale)
  const methodLabel = (id: string, fallback: string) =>
    locale === 'en' ? ((dict.methods as Record<string, string>)[id] ?? fallback) : fallback

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-grid">
          <div className="footer-col">
            <Logo size="sm" locale={locale} />
            <p className="footer-note">{dict.footer.note}</p>
            <div className="footer-contact">
              <a href={phone.href} dir="ltr">{phone.value}</a>
              {EMAIL_METHODS.map((method) => (
                <a key={method.id} href={method.href} dir="ltr">{method.value}</a>
              ))}
            </div>
            <ul className="footer-socials" aria-label={dict.footer.socialsLabel}>
              {SOCIAL_METHODS.map((method) => (
                <li key={method.id}>
                  <a href={method.href} target="_blank" rel="noopener noreferrer">
                    {methodLabel(method.id, method.label)}
                    <span aria-hidden="true"> ↗</span>
                    <span className="sr-only"> ({dict.opensInNewTab})</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
          <nav className="footer-col" aria-label={dict.footer.footerNav}>
            <h2>{dict.footer.quickLinks}</h2>
            <ul>{nav.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
          </nav>
          <nav className="footer-col" aria-label={dict.footer.servicesNav}>
            <h2>{dict.footer.services}</h2>
            <ul>{serviceLinks.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
          </nav>
          <nav className="footer-col" aria-label={dict.footer.legalNav}>
            <h2>{dict.footer.information}</h2>
            <ul>{legalLinks.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
            <ul style={{ marginBlockStart: '.85rem' }}>
              <li><Link href={localeHref(locale, '/contact')}>{dict.footer.contact}</Link></li>
            </ul>
          </nav>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} {dict.footer.copyright}</span>
          <span>{dict.footer.disclaimer}</span>
        </div>
      </div>
    </footer>
  )
}
