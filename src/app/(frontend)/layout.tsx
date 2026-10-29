import type { Metadata } from 'next'
import { SiteShell } from '@/components/site'
import './styles.css'

export const metadata: Metadata = { title: 'Xennic', description: 'زر نور نیرو یکتا | Xennic' }

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fa" dir="rtl"><body><a href="#main-content" className="skip-link">رفتن به محتوای اصلی</a><SiteShell>{children}</SiteShell></body></html>
}
