import Link from 'next/link'
import { RichText } from '@payloadcms/richtext-lexical/react'
import type { RichTextDocument, ServiceCardModel, TrackRecordItemModel } from '@/lib/contracts'
import { faNumber } from '@/lib/home-content'

/**
 * Shared presentation for the content pages.
 *
 * Every page in the redesign uses the same rhythm: a breadcrumb, a page header
 * (eyebrow, one H1, one lede) and then content blocks built from the design
 * system. No page invents copy; the strings come from the approved content in
 * Payload or from the approved copy module.
 */

export function Breadcrumb({ trail }: { trail: { href?: string; label: string }[] }) {
  return (
    <nav aria-label="مسیر صفحه" className="breadcrumb">
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
  children,
}: {
  title: string
  eyebrow?: string
  lead?: string
  trail?: { href?: string; label: string }[]
  children: React.ReactNode
}) {
  return (
    <div className="container page">
      <Breadcrumb trail={trail ?? [{ href: '/', label: 'خانه' }, { label: title }]} />
      <PageHeader eyebrow={eyebrow} title={title} lead={lead} />
      {children}
    </div>
  )
}

export function DocumentContent({ content }: { content: RichTextDocument | null }) {
  return content ? <div className="document-content"><RichText data={content} /></div> : null
}

/** Cards that keep the approved service list readable at every width. */
export function ServiceCards({ services }: { services: ServiceCardModel[] }) {
  return (
    <ul className="card-grid">
      {services.map((service) => (
        <li key={service.id}>
          <Link className="card card--link" href={`/services/${service.slug}`}>
            <div className="card__head">
              <h2 className="card__title">{service.title}</h2>
              {service.comingSoon && <span className="badge">به‌زودی</span>}
            </div>
            {service.summary && <p>{service.summary}</p>}
            <span className="card__more">
              جزئیات خدمت <span aria-hidden="true">←</span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

/**
 * Track-record entries are all pre-company work. The badge and the closing note
 * are part of the approved framing and must stay attached to every entry.
 */
export function TrackRecordList({ items }: { items: TrackRecordItemModel[] }) {
  return (
    <>
      <ol className="timeline">
        {items.map((item, index) => (
          <li className="timeline__item" key={item.id}>
            <span className="timeline__marker" aria-hidden="true">{faNumber(index + 1).padStart(2, '۰')}</span>
            <div className="timeline__body">
              <p className="timeline__badge">پیش از تأسیس Xennic</p>
              <h2 className="timeline__title">{item.title}</h2>
              {item.role && <p className="timeline__role">{item.role}</p>}
              {item.description && <p className="timeline__text">{item.description}</p>}
            </div>
          </li>
        ))}
      </ol>
      <p className="page-note">
        این پیشینه، سابقهٔ حرفه‌ای مؤسس پیش از تأسیس Xennic است و به‌معنای سابقهٔ پروژه‌های شرکت نیست.
      </p>
    </>
  )
}

/** A page that exists in navigation but has no approved content yet. */
export function NotPublished({ title, note }: { title: string; note?: string }) {
  return (
    <div className="notice-card">
      <span className="badge">در حال آماده‌سازی</span>
      <h2 className="h3">این صفحه هنوز منتشر نشده است</h2>
      <p>
        {note ?? `محتوای «${title}» پس از تأیید منتشر می‌شود؛ تا آن زمان برای هر پرسش از مسیرهای تماس استفاده کنید.`}
      </p>
      <Link className="btn btn--glass" href="/contact">
        <span>مسیرهای تماس</span>
        <span className="btn__arrow" aria-hidden="true">←</span>
      </Link>
    </div>
  )
}
