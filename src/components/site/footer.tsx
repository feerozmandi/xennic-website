import Link from 'next/link'
import { Logo } from './logo'
import { navigation } from '../../lib/navigation'

const legal = [
  { href: '/privacy', label: 'حریم خصوصی' },
  { href: '/terms', label: 'شرایط استفاده' },
  { href: '/cookies', label: 'کوکی‌ها' },
]

const services = [
  { href: '/services/industrial-electrical-consulting', label: 'مشاورهٔ برق صنعتی' },
  { href: '/services/building-electrical-design', label: 'طراحی برق ساختمان' },
  { href: '/services/distribution-supervision', label: 'نظارت بر توزیع' },
  { href: '/services/energy-audit', label: 'ممیزی انرژی' },
]

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-grid">
          <div className="footer-col">
            <Logo size="sm" />
            <p className="footer-note">
              زر نور نیرو یکتا (برند تجاری: Xennic) — مهندسی برق قدرت، انرژی و اتوماسیون؛
              مشاوره، طراحی، نظارت و آموزش تخصصی.
            </p>
          </div>
          <nav className="footer-col" aria-label="ناوبری فوتر">
            <h2>دسترسی سریع</h2>
            <ul>{navigation.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
          </nav>
          <nav className="footer-col" aria-label="خدمات در فوتر">
            <h2>خدمات</h2>
            <ul>{services.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
          </nav>
          <nav className="footer-col" aria-label="صفحات حقوقی">
            <h2>اطلاعات</h2>
            <ul>{legal.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
            <ul style={{ marginBlockStart: '.85rem' }}>
              <li><Link href="/contact">مسیرهای تماس</Link></li>
            </ul>
          </nav>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} زر نور نیرو یکتا | Xennic</span>
          <span>محتوای این نسخه صرفاً از منابع تأییدشدهٔ سازمان منتشر می‌شود.</span>
        </div>
      </div>
    </footer>
  )
}
