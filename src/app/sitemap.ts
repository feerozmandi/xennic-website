import type { MetadataRoute } from 'next'
import { INDEXABLE_PATHS, SITE_URL } from '@/lib/seo'

/**
 * Sitemap of the published pages only.
 *
 * The list is explicit, not crawled: a page becomes indexable only when someone
 * adds it here after its content is approved. `/services/[slug]` detail pages are
 * added from the same approved list in `src/lib/approved-copy.ts`.
 */
import { services } from '@/lib/approved-copy'

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date('2026-11-10T00:00:00Z')
  const pages = INDEXABLE_PATHS.map((path) => ({ path }))
  const servicePages = services.filter((service) => !service.comingSoon).map((service) => ({ path: `/services/${service.slug}` }))

  return [...pages, ...servicePages].map(({ path }) => ({
    url: `${SITE_URL}${path === '/' ? '' : path}`,
    lastModified,
    changeFrequency: path === '/' ? 'monthly' : 'yearly',
    priority: path === '/' ? 1 : 0.7,
  }))
}
