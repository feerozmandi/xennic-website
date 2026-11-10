/**
 * Theme tokens as TypeScript values.
 *
 * The CSS in `styles.css` remains the single source of truth for colours.
 * This module only tells the client-side controls which theme names exist and
 * which key the preference is stored under, so no colour value lives twice.
 */
export const THEMES = ['dark', 'light'] as const

export type Theme = (typeof THEMES)[number]

/** Default when the visitor has no stored preference and no OS preference. */
export const DEFAULT_THEME: Theme = 'dark'

/**
 * Storage key. Read by the pre-paint inline script in the root layout, so it
 * must stay in sync with `themeScript` there.
 */
export const THEME_STORAGE_KEY = 'xennic-theme'

/** Cookie mirrored from the preference; kept for future server-side rendering. */
export const THEME_COOKIE_NAME = 'xennic-theme'
