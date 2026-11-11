import type { MetadataRoute } from 'next'
import { INDEXABLE_PATHS, absoluteUrl, twinPath } from '@/lib/seo'
import { services } from '@/lib/approved-copy'

/**
 * Sitemap of the published pages only.
 *
 * The list is explicit, not crawled: a page becomes indexable only when someone
 * adds it here after its content is approved. `/services/[slug]` detail pages are
 * added from the same approved list in `src/lib/approved-copy.ts`.
 *
 * Every entry is listed twice — Persian and English — and each URL declares its
 * twin as an `alternate`, so search engines see one page in two languages rather
 * than two competing pages.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date('2026-11-10T00:00:00Z')
  const paths = [
    ...INDEXABLE_PATHS,
    ...services.filter((service) => !service.comingSoon).map((service) => `/services/${service.slug}`),
  ]
  const languagesFor = (path: string) => ({
    fa: absoluteUrl(twinPath(path, 'fa')),
    en: absoluteUrl(twinPath(path, 'en')),
  })

  return paths.flatMap((path) => {
    const persian = twinPath(path, 'fa')
    return [
      {
        url: absoluteUrl(persian),
        lastModified,
        changeFrequency: persian === '/' ? ('monthly' as const) : ('yearly' as const),
        priority: persian === '/' ? 1 : 0.7,
        alternates: { languages: languagesFor(path) },
      },
      {
        url: absoluteUrl(twinPath(path, 'en')),
        lastModified,
        changeFrequency: path === '/' ? ('monthly' as const) : ('yearly' as const),
        priority: path === '/' ? 1 : 0.7,
        alternates: { languages: languagesFor(path) },
      },
    ]
  })
}
