import type { Metadata } from 'next'

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

export const NO_INDEX: Metadata['robots'] = { index: false, follow: false }

type PageMetaInput = {
  title: string
  description: string
  /** Absolute path on this site, e.g. `/contact`. */
  path: string
  /** When true the page is reachable but must not be indexed. */
  noindex?: boolean
}

/** Title, description, canonical and social card for one public page. */
export function pageMetadata({ title, description, path, noindex = false }: PageMetaInput): Metadata {
  const url = `${SITE_URL}${path === '/' ? '' : path}`
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: 'website',
      locale: 'fa_IR',
      siteName: 'Xennic',
      url,
      title,
      description,
      images: [{ url: `${SITE_URL}/brand/og-cover.png`, width: 1200, height: 630, alt: 'Xennic' }],
    },
    ...(noindex ? { robots: NO_INDEX } : {}),
  }
}
