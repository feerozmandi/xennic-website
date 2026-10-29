import Link from 'next/link'
import type { ReactNode } from 'react'

const navigation = [
  { href: '/company', label: 'شرکت' },
  { href: '/services', label: 'خدمات' },
  { href: '/track-record', label: 'پیشینهٔ مهندسی' },
  { href: '/knowledge', label: 'دانشنامه' },
  { href: '/platform', label: 'Xennic Platform' },
  { href: '/contact', label: 'تماس با ما' },
]

export function SiteShell({ children }: { children: ReactNode }) {
  return <>
    <header className="site-header">
      <div className="container header-inner">
        <Link href="/" className="brand" aria-label="Xennic، صفحهٔ اصلی">Xennic</Link>
        <nav aria-label="ناوبری اصلی"><ul className="nav-list">{navigation.map(item => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul></nav>
      </div>
    </header>
    <main id="main-content">{children}</main>
    <footer className="site-footer"><div className="container footer-inner">
      <span>زر نور نیرو یکتا | Xennic</span>
      <nav aria-label="صفحات حقوقی"><ul className="nav-list">
        <li><Link href="/privacy">حریم خصوصی</Link></li><li><Link href="/terms">شرایط استفاده</Link></li><li><Link href="/cookies">کوکی‌ها</Link></li>
      </ul></nav>
    </div></footer>
  </>
}

export function PlaceholderPage({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="container page">
    <nav aria-label="مسیر صفحه" className="breadcrumb"><Link href="/">خانه</Link><span aria-hidden="true"> / </span><span>{title}</span></nav>
    <h1>{title}</h1>
    <p className="placeholder">ساختار اولیهٔ صفحه؛ محتوا پس از تأیید ساختار افزوده می‌شود.</p>
    {children}
  </div>
}
