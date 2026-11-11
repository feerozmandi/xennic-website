import type { Metadata, Viewport } from 'next'
import { SiteDocument } from '@/components/site'
import { SITE_URL } from '@/lib/seo'
import '../../styles.css'

/**
 * Root layout of the English edition.
 *
 * The English tree is a sibling of the Persian one, not a translation layer on
 * top of it: `/en` has its own `<html lang="en" dir="ltr">`, its own navigation
 * and its own copy, and shares only the design system.
 */
export const metadata: Metadata = {
  title: { default: 'Xennic | Electrical, energy and automation engineering', template: '%s | Xennic' },
  description:
    'Zar-e Noor-e Niroo-e Yekta (Xennic): consultancy, design, supervision and specialist training in power, energy and automation engineering.',
  applicationName: 'Xennic',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'Xennic',
    title: 'Xennic | Electrical, energy and automation engineering',
    description: 'Engineering solutions, consultancy and specialist analysis in electricity, energy and renewables.',
    url: `${SITE_URL}/en`,
    images: [{ url: `${SITE_URL}/brand/og-cover.png`, width: 1200, height: 630, alt: 'Xennic' }],
  },
  alternates: {
    canonical: `${SITE_URL}/en`,
    languages: { fa: SITE_URL, en: `${SITE_URL}/en`, 'x-default': SITE_URL },
  },
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
  return <SiteDocument locale="en">{children}</SiteDocument>
}
