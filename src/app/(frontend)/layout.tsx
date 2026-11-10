import type { Metadata, Viewport } from 'next'
import { SiteShell } from '@/components/site'
import { themeScript } from '@/lib/theme-script'
import './styles.css'

export const metadata: Metadata = {
  title: { default: 'Xennic | مهندسی برق، انرژی و اتوماسیون', template: '%s | Xennic' },
  description:
    'زر نور نیرو یکتا (Xennic): مشاوره، طراحی، نظارت و آموزش تخصصی در حوزهٔ مهندسی برق قدرت، تأسیسات، انرژی و اتوماسیون.',
  applicationName: 'Xennic',
  openGraph: {
    type: 'website',
    locale: 'fa_IR',
    siteName: 'Xennic',
    title: 'Xennic | مهندسی برق، انرژی و اتوماسیون',
    description:
      'راهکارهای مهندسی، مشاوره و تحلیل تخصصی در حوزهٔ برق، انرژی و انرژی‌های تجدیدپذیر.',
  },
  // Canonical host and share image are published once the owner approves the final domain.
}

export const viewport: Viewport = {
  colorScheme: 'dark light',
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#071120' },
    { media: '(prefers-color-scheme: light)', color: '#f4f7fb' },
  ],
}

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <a href="#main-content" className="skip-link">رفتن به محتوای اصلی</a>
        <SiteShell>{children}</SiteShell>
      </body>
    </html>
  )
}
