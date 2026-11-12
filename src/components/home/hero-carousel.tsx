'use client'

/**
 * The hero: a three-slide cover.
 *
 * Each slide is a full-bleed photograph with the copy over it, and the first
 * slide carries the company slogan. The component only decides *which* slide is
 * in view: the copy, the links and the captions arrive as props from
 * `lib/hero-slides.ts`, so no approved sentence is written here.
 *
 * Behaviour that matters for access:
 * - The automatic advance is a convenience, never the only way to reach a
 *   slide: previous/next buttons, one button per slide and the arrow keys all
 *   work, and the pause button is a real toggle that keeps its state.
 * - Auto-advance stops on hover, on keyboard focus inside the hero, in a
 *   background tab and for `prefers-reduced-motion: reduce`.
 * - Slide changes are announced politely, and the active slide's heading is the
 *   page `<h1>`, so the document still has exactly one.
 */
import Image from 'next/image'
import { useCallback, useEffect, useRef, useState } from 'react'
import { getDictionary, type Locale } from '@/lib/i18n'
import type { HeroSlide } from '@/lib/hero-slides'
import { Action, Container } from '../ui/primitives'

type Props = {
  slides: HeroSlide[]
  facts: { value: string; label: string }[]
  locale?: Locale
}

const AUTOPLAY_MS = 7500

export function HeroCarousel({ slides, facts, locale = 'fa' }: Props) {
  const dict = getDictionary(locale)
  const strings = dict.hero
  const total = slides.length
  const [index, setIndex] = useState(0)
  /** The visitor asked for no automatic changes. */
  const [paused, setPaused] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [reducedMotion, setReducedMotion] = useState(false)
  const region = useRef<HTMLElement>(null)

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const sync = () => setReducedMotion(query.matches)
    sync()
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])

  const go = useCallback((next: number) => setIndex(((next % total) + total) % total), [total])

  useEffect(() => {
    if (paused || hovered || focused || reducedMotion || total < 2) return
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') setIndex((current) => (current + 1) % total)
    }, AUTOPLAY_MS)
    return () => window.clearInterval(timer)
  }, [paused, hovered, focused, reducedMotion, total, index])

  const onKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    // Arrow keys belong to the slider only when a control is not using them.
    if ((event.target as HTMLElement).closest('button')) return
    const rtl = dict.dir === 'rtl'
    if (event.key === (rtl ? 'ArrowRight' : 'ArrowLeft')) {
      event.preventDefault()
      go(index - 1)
    } else if (event.key === (rtl ? 'ArrowLeft' : 'ArrowRight')) {
      event.preventDefault()
      go(index + 1)
    }
  }

  return (
    <section
      className="hero"
      aria-labelledby="hero-title"
      aria-roledescription="carousel"
      aria-label={strings.carouselLabel}
      ref={region}
      onKeyDown={onKeyDown}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false)
      }}
    >
      <div className="hero__slides" id="hero-slides">
        {slides.map((slide, i) => {
          const active = i === index
          return (
            <article
              key={slide.id}
              className="hero__slide"
              data-active={active ? 'true' : 'false'}
              aria-hidden={active ? undefined : true}
              aria-roledescription="slide"
              aria-label={strings.slideOf(i + 1, total)}
              // Hidden slides must not be reachable with Tab or read twice.
              inert={!active}
            >
              <div className="hero__art" aria-hidden="true">
                <Image
                  src={slide.image.src}
                  alt=""
                  width={slide.image.width}
                  height={slide.image.height}
                  priority={i === 0}
                  loading={i === 0 ? 'eager' : 'lazy'}
                  sizes="100vw"
                  className="hero__art-image"
                />
              </div>
              <div className="hero__scrim" aria-hidden="true" />
              <Container>
                <div className="hero__layout">
                  <div className="hero__copy">
                    <p className="hero__eyebrow">{slide.eyebrow}</p>
                    {i === 0 ? (
                      <h1 id="hero-title">{slide.title}</h1>
                    ) : (
                      <p className="hero__title" aria-hidden={active ? undefined : true}>{slide.title}</p>
                    )}
                    <p className="hero__summary">{slide.summary}</p>
                    <div className="hero__actions">
                      <Action href={slide.primary.href}>{slide.primary.label}</Action>
                      <Action href={slide.secondary.href} tone="glass">{slide.secondary.label}</Action>
                    </div>
                    <p className="hero__caption">{slide.caption}</p>
                  </div>
                </div>
              </Container>
            </article>
          )
        })}
      </div>

      <Container>
        <div className="hero__strip">
          <dl className="hero__facts" aria-label={strings.factsLabel}>
            {facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
          <p className="hero__note">{strings.note}</p>

          <div className="hero__controls">
            <button type="button" className="hero__arrow" onClick={() => go(index - 1)} aria-label={strings.previous} aria-controls="hero-slides">
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9.5 5.5 16 12l-6.5 6.5" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
            <div className="hero__dots">
              {slides.map((slide, i) => (
                <button
                  key={slide.id}
                  type="button"
                  className="hero__dot"
                  data-active={i === index ? 'true' : 'false'}
                  aria-current={i === index ? 'true' : undefined}
                  aria-label={strings.goTo(i + 1)}
                  onClick={() => go(i)}
                />
              ))}
            </div>
            <button type="button" className="hero__arrow" onClick={() => go(index + 1)} aria-label={strings.next}>
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14.5 5.5 8 12l6.5 6.5" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
            <button
              type="button"
              className="hero__play"
              onClick={() => setPaused((value) => !value)}
              aria-label={paused ? strings.play : strings.pause}
              aria-pressed={paused}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                {paused ? <path d="M8 5.5v13l10-6.5-10-6.5Z" fill="currentColor" /> : <path d="M9 5v14M15 5v14" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />}
              </svg>
            </button>
          </div>
        </div>
      </Container>

      <p className="sr-only" aria-live="polite">{strings.slideChange(index + 1, total, slides[index].title)}</p>
    </section>
  )
}
