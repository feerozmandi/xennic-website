import Link from 'next/link'
import { RichText } from '@payloadcms/richtext-lexical/react'
import type { Page, Service } from '@/payload-types'

export function ContentPage({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="container page">
    <nav aria-label="مسیر صفحه" className="breadcrumb"><Link href="/">خانه</Link><span aria-hidden="true"> / </span><span>{title}</span></nav>
    <h1>{title}</h1>{children}
  </div>
}

export function DocumentContent({ content }: { content: Page['content'] | Service['content'] }) {
  return content ? <div className="document-content"><RichText data={content} /></div> : null
}

export function ServiceCards({ services }: { services: Service[] }) {
  return <div className="cards">{services.map((service) => <Link className="card" href={`/services/${service.slug}`} key={service.id}>
    <h3>{service.title}</h3>{service.comingSoon && <span className="badge">به‌زودی</span>}
    {service.summary && <p>{service.summary}</p>}
  </Link>)}</div>
}
