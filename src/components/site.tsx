import Link from 'next/link'
import type { ReactNode } from 'react'
import { SiteFooter } from './site/footer'
import { SiteHeader } from './site/header'
import { Container } from './ui/primitives'

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main id="main-content">{children}</main>
      <SiteFooter />
    </>
  )
}

export function PlaceholderPage({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Container>
      <div className="page">
        <nav aria-label="مسیر صفحه" className="breadcrumb">
          <Link href="/">خانه</Link>
          <span aria-hidden="true"> / </span>
          <span>{title}</span>
        </nav>
        <h1>{title}</h1>
        <p className="placeholder">ساختار اولیهٔ صفحه؛ محتوا پس از تأیید ساختار افزوده می‌شود.</p>
        {children}
      </div>
    </Container>
  )
}
