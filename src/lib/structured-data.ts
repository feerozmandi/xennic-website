/**
 * JSON-LD for the public site.
 *
 * Two records only, both drawn from approved sources:
 *
 * - `Organization` + `ProfessionalService` for زر نور نیرو یکتا / Xennic,
 *   naming what the approved service list covers, the confirmed telephone and
 *   mailboxes, and the two social profiles the owner published.
 * - `WebSite` for the domain, so the Persian and English trees are one site in
 *   two languages rather than two competing ones.
 *
 * What is deliberately absent: a postal address, opening hours, founding date,
 * employee count, price range, rating, review or award. None of those has an
 * approved source, and structured data is read by machines as a factual claim.
 * When the Vault supplies one, it is added here and nowhere else.
 *
 * `sameAs` is built from `src/lib/contact.ts`, so a profile address can only
 * change in the place that already owns it.
 */
import { EMAIL_METHODS, PHONE_HREF, SOCIAL_METHODS } from './contact'
import { organization, palette } from './design-tokens'
import { SITE_URL, absoluteUrl } from './seo'

type JsonLd = Record<string, unknown>

/** The company as `Organization`, reused as the service's provider. */
function organizationNode() {
  return {
    '@type': 'Organization',
    '@id': `${SITE_URL}/#organization`,
    name: organization.nameFa,
    alternateName: organization.nameEn,
    url: SITE_URL,
    logo: {
      '@type': 'ImageObject',
      url: `${SITE_URL}/brand/xennic-icon.png`,
      width: 512,
      height: 512,
    },
    image: `${SITE_URL}/brand/og-cover.png`,
    telephone: PHONE_HREF.replace('tel:', ''),
    email: EMAIL_METHODS.map((method) => method.value),
    sameAs: SOCIAL_METHODS.map((method) => method.href),
    knowsLanguage: ['fa-IR', 'en'],
  }
}

/**
 * The homepage graph: the company, the professional service it offers and the
 * website itself, all one `@graph` so the nodes reference each other by `@id`
 * instead of repeating.
 *
 * `areaServed` is the four provinces the approved biography names. It is a
 * statement about where the founder has worked, not a claim of an office there,
 * which is why no `address` is emitted.
 */
export function homeStructuredData(): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      organizationNode(),
      {
        '@type': 'ProfessionalService',
        '@id': `${SITE_URL}/#service`,
        name: `${organization.nameFa} (${organization.nameEn})`,
        url: SITE_URL,
        provider: { '@id': `${SITE_URL}/#organization` },
        description:
          'مشاوره، طراحی و نظارت در مهندسی برق قدرت، تأسیسات برق ساختمان، شبکهٔ توزیع، انرژی‌های تجدیدپذیر و ممیزی انرژی.',
        serviceType: organization.services,
        areaServed: [
          { '@type': 'AdministrativeArea', name: 'استان قم' },
          { '@type': 'AdministrativeArea', name: 'استان تهران' },
          { '@type': 'AdministrativeArea', name: 'استان مازندران' },
          { '@type': 'AdministrativeArea', name: 'استان اصفهان' },
        ],
        availableLanguage: ['fa', 'en'],
      },
      {
        '@type': 'WebSite',
        '@id': `${SITE_URL}/#website`,
        url: SITE_URL,
        name: organization.nameEn,
        alternateName: organization.nameFa,
        inLanguage: ['fa-IR', 'en'],
        publisher: { '@id': `${SITE_URL}/#organization` },
      },
    ],
  }
}

/** The company alone, for pages that are about it rather than the whole site. */
export function organizationStructuredData(): JsonLd {
  return { '@context': 'https://schema.org', '@graph': [organizationNode()] }
}

/**
 * A trail for one page, in the page's own language.
 *
 * Only routes that exist and are published are passed in by the caller; the
 * home crumb is added here so no page forgets it.
 */
export function breadcrumbStructuredData(items: { name: string; path: string }[], homeLabel: string): JsonLd {
  const trail = [{ name: homeLabel, path: '/' }, ...items]
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: trail.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  }
}

/**
 * The platform page: the calculators as a `SoftwareApplication`, offered by the
 * company, plus the trail that leads to it.
 *
 * `applicationCategory` is the closest published schema.org category, and
 * `offers` states the one thing that is true — the tools are free to use on the
 * site. No version, rating, download or operating system claim is made.
 */
export function softwareApplicationLd(): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    '@id': `${SITE_URL}/platform#application`,
    name: 'Xennic Platform — محاسبه‌گرهای مهندسی برق',
    url: absoluteUrl('/platform'),
    applicationCategory: 'https://schema.org/EngineeringApplication',
    applicationSubCategory: 'محاسبه‌گر مهندسی برق، انرژی و ارتینگ',
    operatingSystem: 'Web',
    inLanguage: 'fa-IR',
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'IRR' },
    publisher: { '@id': `${SITE_URL}/#organization` },
    description:
      'محاسبهٔ ظرفیت بانک خازنی و اصلاح ضریب توان در ۴۰۰ ولت، تخمین فنی نیروگاه خورشیدی، و ارزیابی اولیهٔ ممیزی انرژی و ارتینگ.',
  }
}

/** The theme colour a browser paints its chrome with; one palette, two themes. */
export const THEME_COLORS = { dark: palette.ink, light: palette.paper } as const
