import Link from 'next/link'
import type { ReactNode } from 'react'

/** Shared, presentation-only building blocks. No data access belongs here. */
export function Container({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`container ${className}`.trim()}>{children}</div>
}

export function Section({ children, id, tone = 'plain', tight = false }: {
  children: ReactNode
  id?: string
  tone?: 'plain' | 'glass'
  tight?: boolean
}) {
  return (
    <section id={id} className={`section${tight ? ' section--tight' : ''}`}>
      {tone === 'glass'
        ? <Container><div className="glass glass--quiet" style={{ padding: 'clamp(1.25rem, 3vw, 2.5rem)' }}>{children}</div></Container>
        : <Container>{children}</Container>}
    </section>
  )
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="eyebrow">{children}</span>
}

export function SectionHeading({ eyebrow, title, lead, id }: {
  eyebrow?: string
  title: string
  lead?: string
  id?: string
}) {
  return (
    <header style={{ display: 'grid', gap: '.7rem', maxWidth: '62ch', marginBlockEnd: 'clamp(1.5rem, 3vw, 2.25rem)' }}>
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="h2" id={id}>{title}</h2>
      {lead && <p className="lede">{lead}</p>}
    </header>
  )
}

type ActionProps = {
  href: string
  children: ReactNode
  tone?: 'primary' | 'glass'
  arrow?: boolean
  ariaLabel?: string
}

export function Action({ href, children, tone = 'primary', arrow = true, ariaLabel }: ActionProps) {
  return (
    <Link href={href} className={`btn btn--${tone}`} aria-label={ariaLabel}>
      <span>{children}</span>
      {arrow && <span className="btn__arrow" aria-hidden="true">←</span>}
    </Link>
  )
}
