import Image from 'next/image'
import Link from 'next/link'
import { RichText } from '@payloadcms/richtext-lexical/react'
import type { Illustration } from '@/lib/imagery'
import { serviceImage } from '@/lib/imagery'
import type { RichTextDocument, ServiceCardModel, TrackRecordItemModel } from '@/lib/contracts'
import { faNumber } from '@/lib/home-content'
import { getDictionary, localeHref, type Locale } from '@/lib/i18n'

/**
 * Shared presentation for the content pages.
 *
 * Every page in the redesign uses the same rhythm: a breadcrumb, a page header
 * (eyebrow, one H1, one lede) and then content blocks built from the design
 * system. No page invents copy; the strings come from the approved content in
 * Payload or from the approved copy module.
 *
 * `locale` only decides interface strings and link prefixes. The body text is
 * whatever the page passed in, so the Persian and English trees can use the same
 * components without sharing a content source.
 */

export function Breadcrumb({ trail, locale = 'fa' }: { trail: { href?: string; label: string }[]; locale?: Locale }) {
  const dict = getDictionary(locale)
  return (
    <nav aria-label={dict.breadcrumb} className="breadcrumb">
      {trail.map((crumb, index) => (
        <span key={`${crumb.label}-${index}`} className="breadcrumb__item">
          {crumb.href ? <Link href={crumb.href}>{crumb.label}</Link> : <span aria-current="page">{crumb.label}</span>}
          {index < trail.length - 1 && <span aria-hidden="true" className="breadcrumb__sep">/</span>}
        </span>
      ))}
    </nav>
  )
}

export function PageHeader({
  eyebrow,
  title,
  lead,
  meta,
}: {
  eyebrow?: string
  title: string
  lead?: string
  meta?: string
}) {
  return (
    <header className="page-head">
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h1 className="h1">{title}</h1>
      {lead && <p className="lede">{lead}</p>}
      {meta && <p className="page-head__meta">{meta}</p>}
    </header>
  )
}

export function ContentPage({
  title,
  eyebrow,
  lead,
  trail,
  locale = 'fa',
  media,
  children,
}: {
  title: string
  eyebrow?: string
  lead?: string
  trail?: { href?: string; label: string }[]
  locale?: Locale
  /** Optional illustration band under the page header. */
  media?: Illustration
  children: React.ReactNode
}) {
  const dict = getDictionary(locale)
  return (
    <div className="container page">
      <Breadcrumb
        locale={locale}
        trail={trail ?? [{ href: localeHref(locale, '/'), label: dict.home }, { label: title }]}
      />
      <PageHeader eyebrow={eyebrow} title={title} lead={lead} />
      {media && <Figure image={media} locale={locale} priority />}
      {children}
    </div>
  )
}

export function DocumentContent({ content }: { content: RichTextDocument | null }) {
  return content ? <div className="document-content"><RichText data={content} /></div> : null
}

/**
 * Plain heading/paragraph body. The English edition is authored as data rather
 * than as CMS rich text, so it needs the same rhythm without a Lexical document.
 */
export function BlockContent({ blocks }: { blocks: readonly { heading: string; text: string }[] }) {
  return (
    <div className="document-content">
      {blocks.map((block) => (
        <section key={block.heading}>
          <h2>{block.heading}</h2>
          <p>{block.text}</p>
        </section>
      ))}
    </div>
  )
}

/**
 * Service cards.
 *
 * Each card carries an illustration of the field the service works in. The
 * pictures are generated illustrations, never photographs of a specific project,
 * so the grid always ends with the note that says exactly that.
 */
export function ServiceCards({ services, locale = 'fa' }: { services: ServiceCardModel[]; locale?: Locale }) {
  const dict = getDictionary(locale)
  return (
    <>
      <ul className="card-grid" data-reveal-group>
        {services.map((service) => {
          const image = serviceImage(service.slug)
          return (
            <li key={service.id} data-reveal>
              <Link className="card card--link card--media" href={localeHref(locale, `/services/${service.slug}`)}>
                {image && (
                  <span className="card__media">
                    <Image
                      src={image.src}
                      alt=""
                      width={image.width}
                      height={image.height}
                      sizes="(max-width: 639px) 92vw, (max-width: 1023px) 46vw, 380px"
                      className="card__media-art"
                    />
                  </span>
                )}
                <span className="card__body">
                  <span className="card__head">
                    <h2 className="card__title">{service.title}</h2>
                    {service.comingSoon && <span className="badge">{dict.comingSoon}</span>}
                  </span>
                  {service.summary && <p>{service.summary}</p>}
                  <span className="card__more">
                    {dict.servicesSection.more} <span className="arrow" aria-hidden="true">←</span>
                  </span>
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
      <p className="grid-note">{dict.servicesSection.imageNote}</p>
    </>
  )
}

/**
 * A picture with its caption. `aria-hidden` is not used: the caption describes
 * what the picture is, and that description is the point.
 */
export function Figure({ image, locale = 'fa', priority = false }: { image: Illustration; locale?: Locale; priority?: boolean }) {
  return (
    <figure className="page-figure glass glass--quiet" data-reveal>
      <Image
        src={image.src}
        alt={image.alt[locale]}
        width={image.width}
        height={image.height}
        priority={priority}
        sizes="(max-width: 899px) 92vw, 900px"
        className="page-figure__art"
      />
      <figcaption>{image.caption[locale]}</figcaption>
    </figure>
  )
}

/**
 * Track-record entries are all pre-company work. The badge and the closing note
 * are part of the approved framing and must stay attached to every entry.
 */
export function TrackRecordList({ items, locale = 'fa' }: { items: TrackRecordItemModel[]; locale?: Locale }) {
  const dict = getDictionary(locale)
  const marker = (index: number) =>
    locale === 'en' ? String(index + 1).padStart(2, '0') : faNumber(index + 1).padStart(2, '۰')
  return (
    <>
      <ol className="timeline" data-reveal-group>
        {items.map((item, index) => (
          <li className="timeline__item" key={item.id} data-reveal>
            <span className="timeline__marker" aria-hidden="true">{marker(index)}</span>
            <div className="timeline__body">
              <p className="timeline__badge">{dict.content.recordBadge}</p>
              <h2 className="timeline__title">{item.title}</h2>
              {item.role && <p className="timeline__role">{item.role}</p>}
              {item.description && <p className="timeline__text">{item.description}</p>}
            </div>
          </li>
        ))}
      </ol>
      <p className="page-note">{dict.content.recordNote}</p>
    </>
  )
}

/** A page that exists in navigation but has no approved content yet. */
export function NotPublished({
  title,
  note,
  locale = 'fa',
}: {
  title: string
  note?: string
  locale?: Locale
}) {
  const dict = getDictionary(locale)
  return (
    <div className="notice-card" data-reveal>
      <span className="badge">{dict.notPublishedBadge}</span>
      <h2 className="h3">{dict.notPublishedTitle}</h2>
      <p>{note ?? dict.notPublishedBody(title)}</p>
      <Link className="btn btn--glass" href={localeHref(locale, '/contact')}>
        <span>{dict.contactRoutes}</span>
        <span className="btn__arrow" aria-hidden="true">←</span>
      </Link>
    </div>
  )
}
