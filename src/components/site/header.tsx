'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import { navigation } from '../../lib/navigation'
import { LocaleSwitch } from './locale-switch'
import { Logo } from './logo'
import { ThemeToggle } from './theme-toggle'

export function SiteHeader() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const sheetRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    const toggle = toggleRef.current
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        setOpen(false)
        return
      }
      if (event.key !== 'Tab' || !sheetRef.current) return
      const nodes = Array.from(
        sheetRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'),
      ).filter((node) => node.offsetParent !== null)
      if (nodes.length === 0) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      toggle?.focus()
    }
  }, [open])

  return (
    <>
      <header className="site-header">
        <div className="container">
          <div className="glass glass--quiet header-bar">
            <Logo size="sm" />
            <nav className="nav-desktop" aria-label="ناوبری اصلی">
              <ul>
                {navigation.map((item) => (
                  <li key={item.href}>
                    <Link href={item.href} aria-current={pathname === item.href ? 'page' : undefined}>
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
            <div className="header-actions">
              <div className="header-locale">
                <LocaleSwitch compact />
              </div>
              <ThemeToggle />
              <Link href="/contact" className="btn btn--primary header-cta">
                درخواست مشاوره
              </Link>
              <button
                ref={toggleRef}
                type="button"
                className="menu-toggle"
                aria-expanded={open}
                aria-controls="mobile-navigation"
                aria-label={open ? 'بستن منو' : 'باز کردن منو'}
                onClick={() => setOpen((value) => !value)}
              >
                <span className="menu-toggle__bars" aria-hidden="true"><span /><span /><span /></span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {open && (
        <div className="mobile-sheet" role="dialog" aria-modal="true" aria-label="منوی اصلی" ref={sheetRef}>
          <div className="mobile-sheet__top">
            <Logo size="sm" />
            <button ref={closeRef} type="button" className="menu-toggle" onClick={() => setOpen(false)} aria-label="بستن منو">
              <span aria-hidden="true">✕</span>
            </button>
          </div>
          <div className="mobile-sheet__panel">
            <div className="mobile-sheet__controls">
              <LocaleSwitch />
              <ThemeToggle />
            </div>
            <nav className="mobile-nav" id="mobile-navigation" aria-label="ناوبری موبایل">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={pathname === item.href ? 'page' : undefined}
                  onClick={() => setOpen(false)}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <Link href="/contact" className="btn btn--primary" onClick={() => setOpen(false)}>درخواست مشاوره</Link>
            <p className="mobile-sheet__meta">زر نور نیرو یکتا | Xennic — مهندسی برق، انرژی و اتوماسیون</p>
          </div>
        </div>
      )}
    </>
  )
}
