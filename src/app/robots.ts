import type { MetadataRoute } from 'next'
import { NOT_PUBLISHED_PATHS, SITE_URL } from '@/lib/seo'

/**
 * Crawl policy.
 *
 * The preview deployment must never be indexed at all: it runs with
 * `XENNIC_PREVIEW=1`, so the whole site is disallowed there and the sitemap is
 * not advertised. Production keeps the private surfaces out and leaves the
 * public pages open.
 */
export default function robots(): MetadataRoute.Robots {
  if (process.env.XENNIC_PREVIEW === '1') {
    return { rules: [{ userAgent: '*', disallow: '/' }] }
  }

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/admin', '/api/', '/health', ...NOT_PUBLISHED_PATHS.filter((path) => path !== '/platform')],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  }
}
