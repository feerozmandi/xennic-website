'use client'

/**
 * The Declare island.
 *
 * The platform's three calculators are not React. They are a Declare program,
 * compiled ahead of time into `declare-apps/xennic-platform/dist/` by
 * `declarec`, and this component is the whole of the bridge: a sized box
 * marked `data-declare-embed` (the marker is the contract — the app fills the
 * element, not the window), and a dynamic import of the prebuilt bundle.
 *
 * Three decisions are worth keeping in view:
 *
 *   1. **Nothing is fetched until the box is near the viewport.**
 *      `IntersectionObserver` with a generous root margin is the trigger, and a
 *      reader who prefers reduced data gets a button instead of a load.
 *   2. **The bundle name comes from the build.** `declarec` names the file
 *      after a hash of its content, so a hardcoded name would rot on the first
 *      rebuild. `scripts/declare-platform.mjs` writes the name into a generated
 *      module before the build and copies the program into the build's own
 *      static directory after it — `/_next/static/declare-platform/…`, a path
 *      the public edge already serves.
 *   3. **The page owns the page.** The app paints only inside its box and does
 *      not touch the document's theme, scroll position or history. It follows
 *      the site's theme instead of owning one, and it asks for exactly one
 *      thing in return: that its figures travel with the request.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { DECLARE_PLATFORM_PATH } from '@/lib/declare-platform.generated'
import { getDictionary, type Locale } from '@/lib/i18n'
import { contactHref, requestSummary, type PlatformRequest } from '@/lib/platform-handoff'
import type { Theme } from '@/lib/theme'

type Tenant = {
  provide: (name: string, value: unknown) => void
  exposed: (name: string, fallback: unknown) => unknown
}

/** What the program posts to the page. */
type HostMessage = { topic: string; payload?: PlatformRequest }

type Phase = 'idle' | 'loading' | 'ready' | 'failed'

function currentTheme(): Theme {
  if (typeof document === 'undefined') return 'dark'
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}

export function DeclarePlatformIsland({ locale = 'fa' }: { locale?: Locale }) {
  const dict = getDictionary(locale).platformIsland
  const router = useRouter()
  const hostRef = useRef<HTMLDivElement>(null)
  const tenantRef = useRef<Tenant | null>(null)
  const bootedRef = useRef(false)
  const [phase, setPhase] = useState<Phase>('idle')

  /**
   * Boot the app. Idempotent: the observer, the button and a late callback may
   * all ask for it, and exactly one boot happens.
   */
  const boot = useCallback(async () => {
    if (bootedRef.current) return
    const host = hostRef.current
    if (!host) return
    bootedRef.current = true
    setPhase('loading')

    try {
      // A static file with a hashed name. `webpackIgnore` keeps the bundler out
      // of it: the URL is resolved at runtime, and the file is a build artifact
      // rather than a module of the site.
      // The development server has no build output, so it serves the program
      // from `public/` and says so through the environment.
      const url = process.env.NEXT_PUBLIC_DECLARE_PLATFORM_URL ?? DECLARE_PLATFORM_PATH
      const bundle = await import(/* webpackIgnore: true */ url)
      const tenant = (await bundle.default({
        host,
        // The app reads this with `app.hostProvided("dark", false)`.
        provides: { dark: currentTheme() === 'dark' },
        onPost: (message: HostMessage) => {
          // The program asks for one thing: that its numbers travel with the
          // request. The page writes them into the contact form's own fields
          // and sends the reader there.
          if (message.topic === 'request') {
            const summary = requestSummary(message.payload ?? {}, dict.handoff, locale)
            router.push(contactHref(locale, dict.handoff.subject, summary))
          }
        },
      })) as Tenant

      tenantRef.current = tenant
      setPhase('ready')
    } catch (error) {
      // A failed boot leaves an honest message and a retry — never an empty
      // frame and never a hidden failure.
      console.error('declare: boot failed', error)
      setPhase('failed')
    }
  }, [dict.handoff, locale, router])

  /** Load when the box is within a screen and a half of the viewport. */
  useEffect(() => {
    const host = hostRef.current
    if (!host || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          observer.disconnect()
          void boot()
        }
      },
      { rootMargin: '600px 0px' },
    )
    observer.observe(host)
    return () => observer.disconnect()
  }, [boot])

  /** Follow the page's theme for as long as the app lives. */
  useEffect(() => {
    const observer = new MutationObserver(() => {
      tenantRef.current?.provide('dark', currentTheme() === 'dark')
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  /**
   * Start the app by hand.
   *
   * There is only ever one instance in the box: the button is gone once the
   * app is running, so a second boot cannot stack a second panel on the first.
   */
  const start = () => {
    if (phase === 'ready') return
    bootedRef.current = false
    void boot()
  }

  return (
    <div className="declare-island">
      <div className="declare-island__bar">
        <p className="declare-island__hint">{dict.hint}</p>
        {phase === 'idle' && (
          <button type="button" className="btn btn--glass" onClick={start}>
            <span>{dict.load}</span>
          </button>
        )}
      </div>

      <div
        ref={hostRef}
        className="declare-island__host"
        data-declare-embed
        data-declare-phase={phase}
      >
        {phase === 'failed' && (
          <div className="declare-island__fallback" role="alert">
            <p>{dict.failed}</p>
            <button type="button" className="btn btn--glass" onClick={start}>
              <span>{dict.retry}</span>
            </button>
          </div>
        )}
        {phase !== 'ready' && phase !== 'failed' && (
          <p className="declare-island__loading" role="status" aria-live="polite">
            {phase === 'loading' ? dict.loading : dict.idle}
          </p>
        )}
      </div>

      <ul className="declare-island__notes">
        {dict.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  )
}
