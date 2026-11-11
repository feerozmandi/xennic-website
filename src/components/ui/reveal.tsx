'use client'

/**
 * Scroll reveal.
 *
 * Any element marked `data-reveal` fades and rises into place when it enters the
 * viewport, and settles back when it leaves so the effect is visible again on the
 * way up as well as the way down. Three rules keep it honest:
 *
 *  1. **No JavaScript, no hiding.** The hidden state is scoped to
 *     `html.has-js`, which a pre-paint script adds. If the bundle never runs,
 *     everything is simply visible.
 *  2. **Reduced motion wins.** The stylesheet only applies the transition inside
 *     `@media (prefers-reduced-motion: no-preference)`; this component stays out
 *     of the way when the user asked for less movement.
 *  3. **Works after client-side navigation.** A `MutationObserver` picks up the
 *     nodes that App Router renders later, so a page opened from the menu
 *     animates exactly like a full load.
 *
 * The element index inside its nearest group (`[data-reveal-group]`) becomes the
 * delay, which gives a staggered entrance without any per-element prop.
 */
import { useEffect } from 'react'

const REVEALED = 'is-revealed'
const MAX_STAGGER = 7

export function RevealController() {
  useEffect(() => {
    const root = document.documentElement
    // Set again here so a stale attribute in the served HTML cannot hide content.
    root.classList.add('has-js')

    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      root.classList.add('reveal-off')
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const element = entry.target as HTMLElement
          if (entry.isIntersecting) {
            element.classList.add(REVEALED)
          } else if (entry.boundingClientRect.top > 0) {
            // Only reset below the fold: content scrolled past stays visible.
            element.classList.remove(REVEALED)
          }
        }
      },
      { rootMargin: '0px 0px -12% 0px', threshold: 0.12 },
    )

    const watched = new WeakSet<Element>()

    const register = () => {
      let index = 0
      for (const element of document.querySelectorAll<HTMLElement>('[data-reveal]')) {
        if (watched.has(element)) continue
        const group = element.closest('[data-reveal-group]')
        const siblings = group
          ? Array.from(group.querySelectorAll<HTMLElement>('[data-reveal]'))
          : [element]
        index = siblings.indexOf(element)
        element.style.setProperty('--reveal-delay', `${Math.min(Math.max(index, 0), MAX_STAGGER) * 65}ms`)
        watched.add(element)
        observer.observe(element)
      }
    }

    register()
    const mutations = new MutationObserver(register)
    mutations.observe(document.body, { childList: true, subtree: true })

    return () => {
      mutations.disconnect()
      observer.disconnect()
    }
  }, [])

  return null
}
