import type { Metadata, Viewport } from 'next'
import { SiteShell } from '@/components/site'
import { SITE_URL } from '@/lib/seo'
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
    url: SITE_URL,
    images: [{ url: `${SITE_URL}/brand/og-cover.png`, width: 1200, height: 630, alt: 'Xennic' }],
  },
  alternates: { canonical: SITE_URL },
  icons: {
    icon: [
      { url: '/icon.png', sizes: '192x192', type: 'image/png' },
      { url: '/brand/xennic-icon.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: [{ url: '/apple-icon.png', sizes: '180x180', type: 'image/png' }],
  },
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
