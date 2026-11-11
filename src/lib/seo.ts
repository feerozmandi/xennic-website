import type { Metadata } from 'next'
import type { Locale } from './i18n'

/**
 * SEO policy for the public site.
 *
 * Indexable: the pages that carry approved content and are linked from the main
 * navigation. Not indexable: the admin panel, the Payload API, the health probe
 * and every "not published yet" placeholder. The same split is applied in three
 * places so a single mistake cannot publish an incomplete page:
 *   1. `robots.ts` (crawl rules),
 *   2. per-page `noindex` metadata,
 *   3. `next.config.ts` response headers for `/admin` and `/api`.
 *
 * Every page exists twice — `/…` in Persian and `/en/…` in English — so each
 * metadata set also declares the pair as `hreflang` alternates. A twin page is a
 * translation, never a duplicate: the canonical always points at the page's own
 * language, and `x-default` points at Persian.
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? 'https://xennic.ir').replace(/\/$/, '')

/**
 * Paths that are linked but not published. They must never be indexed and must
 * never appear in the sitemap; the crawler should reach them only by direct link.
 */
export const NOT_PUBLISHED_PATHS = ['/knowledge', '/platform', '/privacy', '/terms', '/cookies', '/tools'] as const

export const INDEXABLE_PATHS = ['/', '/company', '/company/team', '/services', '/track-record', '/contact'] as const

export function isNotPublished(path: string) {
  return (NOT_PUBLISHED_PATHS as readonly string[]).includes(path)
}

/** The same path in the other language: `/contact` ↔ `/en/contact`. */
export function twinPath(path: string, locale: Locale): string {
  const isEnglish = path === '/en' || path.startsWith('/en/')
  const base = isEnglish ? (path === '/en' ? '/' : path.slice(3)) : path
  return locale === 'en' ? (base === '/' ? '/en' : `/en${base}`) : base
}

export function absoluteUrl(path: string): string {
  return `${SITE_URL}${path === '/' ? '' : path}`
}

export const NO_INDEX: Metadata['robots'] = { index: false, follow: false }

type PageMetaInput = {
  title: string
  description: string
  /** Absolute path on this site in the page's own language, e.g. `/contact`. */
  path: string
  /** When true the page is reachable but must not be indexed. */
  noindex?: boolean
  /** Language of the page; decides canonical, Open Graph locale and dir. */
  locale?: Locale
}

/** Title, description, canonical, hreflang pair and social card for one page. */
export function pageMetadata({ title, description, path, noindex = false, locale = 'fa' }: PageMetaInput): Metadata {
  const url = absoluteUrl(path)
  const persian = twinPath(path, 'fa')
  const english = twinPath(path, 'en')
  return {
    title,
    description,
    alternates: {
      canonical: url,
      languages: {
        fa: absoluteUrl(persian),
        en: absoluteUrl(english),
        'x-default': absoluteUrl(persian),
      },
    },
    openGraph: {
      type: 'website',
      locale: locale === 'en' ? 'en_US' : 'fa_IR',
      siteName: 'Xennic',
      url,
      title,
      description,
      images: [{ url: `${SITE_URL}/brand/og-cover.png`, width: 1200, height: 630, alt: 'Xennic' }],
    },
    ...(noindex ? { robots: NO_INDEX } : {}),
  }
}
