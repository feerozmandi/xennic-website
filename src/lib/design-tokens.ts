/**
 * Brand palette, as values rather than CSS custom properties.
 *
 * `src/app/styles.css` owns the design tokens for the rendered page. A few
 * places cannot read CSS variables — JSON-LD records, the Open Graph card, the
 * browser `theme-color` — and they must not invent a second palette. Those read
 * the values here, so a colour changes in one commit or not at all.
 *
 * `docs/reports/2026-11-25-phase-1-declare-and-bento-plan.md` records why these
 * are the palette the site shipped with and not the hex codes in the brief.
 */
export const palette = {
  /** Deep grid navy: the page behind everything. */
  ink: '#071120',
  /** The card surface at night. */
  ink2: '#0d1b2a',
  /** Solar gold ("zar" + "nur"): primary calls to action and key figures. */
  gold: '#f5b400',
  goldSoft: '#ffd166',
  /** Electric cyan ("niru" + smart systems): diagrams and the platform. */
  teal: '#2dd4bf',
  /** Paper: the light theme's page surface. */
  paper: '#f6f8fb',
  /** Text on a gold button. */
  onGold: '#23180a',
  /** Body text at night, and its muted companion. */
  textNight: '#eef3fa',
  textMutedNight: '#b3c0d1',
  /** Body text by day, and its muted companion. */
  textDay: '#0b1a2b',
  textMutedDay: '#4a5a6d',
} as const

/**
 * Structured-data identity for the company.
 *
 * Only facts an approved source states: the Persian and English names, what the
 * company does, the confirmed telephone and addresses, and the two social
 * profiles. No address, opening hours, founding date, employee count, rating or
 * award appears — none of those is approved, and inventing them in structured
 * data is the same lie as printing them on the page.
 */
export const organization = {
  nameFa: 'زر نور نیرو یکتا',
  nameEn: 'Xennic',
  /** Areas the approved service list covers, in the words of that list. */
  services: [
    'مشاورهٔ فنی برق صنعتی',
    'طراحی تأسیسات برق ساختمان',
    'نظارت فنی بر پروژه‌های شبکهٔ توزیع',
    'ممیزی انرژی و بهینه‌سازی مصرف',
    'طراحی سیستم ارتینگ و صاعقه‌گیر',
    'آموزش‌های تخصصی فنی',
  ],
} as const
