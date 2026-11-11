'use client'

import { useSyncExternalStore } from 'react'
import { getDictionary, type Locale } from '@/lib/i18n'
import { THEME_COOKIE_NAME, THEME_STORAGE_KEY, type Theme } from '@/lib/theme'

/**
 * The document element is the single source of truth for the active theme: the
 * pre-paint script writes it, and this switch both reads and writes it. React
 * subscribes instead of mirroring the value in state, so the server render and
 * the hydrated client can never disagree.
 */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  return () => observer.disconnect()
}

function getSnapshot(): boolean {
  return document.documentElement.dataset.theme === 'light'
}

/** Server render assumes the brand default (dark); the client corrects itself. */
function getServerSnapshot(): boolean {
  return false
}

function setTheme(next: Theme) {
  document.documentElement.dataset.theme = next
  document.documentElement.style.colorScheme = next
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, next)
  } catch {
    // Private mode or blocked storage: the attribute still drives this page.
  }
  document.cookie = `${THEME_COOKIE_NAME}=${next}; path=/; max-age=31536000; samesite=lax`
}

export function ThemeToggle({ locale = 'fa' }: { locale?: Locale }) {
  const isLight = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
  const dict = getDictionary(locale)

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isLight}
      aria-label={isLight ? dict.theme.toDark : dict.theme.toLight}
      className="liquid-switch"
      onClick={() => setTheme(isLight ? 'dark' : 'light')}
    >
      <span className="liquid-switch__track" aria-hidden="true">
        <span className="liquid-switch__sky" />
        <span className="liquid-switch__stars" />
        <span className="liquid-switch__clouds" />
      </span>
      <span className="liquid-switch__knob" aria-hidden="true">
        <span className="liquid-switch__knob-inner" />
        <span className="liquid-switch__mark liquid-switch__mark--sun">☀</span>
        <span className="liquid-switch__mark liquid-switch__mark--moon">☾</span>
      </span>
      <span className="sr-only" aria-live="polite">
        {isLight ? dict.theme.lightOn : dict.theme.darkOn}
      </span>
    </button>
  )
}
