/**
 * English edition of the approved copy.
 *
 * Every entry is a translation of an approved Persian source — `approved-copy.ts`
 * (L2-MKT-004 v0.2.1) — and adds no claim, credential, client or contact detail
 * of its own. The CMS stores Persian only, so until it gains translated fields
 * (which needs a migration) the English edition lives here, next to the Persian
 * source it mirrors, so both can be reviewed side by side.
 *
 * Rules for editing: keep the sentence-level structure of the Persian source so
 * a reviewer can diff the two; never localise a proper noun that the company
 * uses untranslated (Xennic, IEC, Mabhas 13); never introduce a figure that is
 * not in the Persian sentence above it.
 */
import type { ServiceCardModel, TeamMemberModel, TrackRecordItemModel } from './contracts'
import type { Block, HomeContent } from './home-content'
import { FOUNDER_NAME } from './home-content'

export const en = {
  founderName: FOUNDER_NAME,
  founderNameLatin: 'Ahmad Firouzmandi',
  /** The leading clause of the biography, matching `FOUNDER_HEADLINE` in `contact.ts`. */
  founderHeadline: 'A power engineer with nearly four decades of hands-on experience in Iran’s electricity industry',

  founderBio:
    'Ahmad Firouzmandi — a power engineer with nearly four decades of hands-on experience in Iran’s electricity industry; a specialist in distribution networks, live-line work, dispatching, and the design of industrial and building electrical installations. Member of the Qom Province Construction Engineering Organisation. Professional activity across Qom, Tehran, Mazandaran and Isfahan. Alongside engineering practice, founder and developer of the online store “Salnameh-ye Now” (salenoo.ir) and active in artificial intelligence and process automation — the same background that shaped the “traditional engineering + intelligent technology” combination on which Xennic’s mission rests.',

  homeTitle: 'Energy engineering for sharper decisions and a smarter future',
  homeSummary:
    'Zar-e Noor-e Niroo-e Yekta works in electrical engineering, energy and renewable energy, offering engineering solutions, consultancy and specialist analysis, built on engineering knowledge and modern technology.',

  principles: [
    { heading: 'Engineering First', text: 'Decisions follow engineering principles and standards' },
    { heading: 'Evidence Based', text: 'Results grounded in data, sources and evidence' },
    { heading: 'Technology Enabled', text: 'Software, AI and digital tools in everyday practice' },
    { heading: 'Independent Thinking', text: 'Focused on analysis and solutions, not on selling a product' },
    { heading: 'Long-Term Perspective', text: 'Solutions that look at energy and infrastructure over the long run' },
  ] satisfies Block[],

  aboutBlocks: [
    {
      heading: 'Mission',
      text: 'Zar-e Noor-e Niroo-e Yekta (trade name: Xennic) draws on engineering knowledge, professional expertise and continuous innovation to deliver comprehensive consultancy, design, supervision and execution in power engineering, automation and renewable energy.',
    },
    {
      heading: 'Vision',
      text: 'Over the long term, Zar-e Noor-e Niroo-e Yekta aims to become one of the trusted references for electrical and energy engineering services in Iran — a name that stands for trust, knowledge, quality and engineering innovation.',
    },
    { heading: 'Intelligent engineering', text: 'Combining engineering knowledge with technology and artificial intelligence' },
    { heading: 'Quality', text: 'Committed to precision and standards across every service' },
    { heading: 'Trust', text: 'Honesty and transparency in every client relationship' },
    { heading: 'Foresight', text: 'Solutions with a long view of energy and infrastructure' },
    { heading: 'Continuous learning', text: 'Technical knowledge kept current with the latest standards' },
  ] satisfies Block[],

  trackRecordIntro: {
    title: 'Engineering experience you can rely on',
    summary: 'The professional experience and record of Xennic’s founder in the electricity industry, before this company was established.',
  },

  services: [
    {
      slug: 'industrial-electrical-consulting',
      title: 'Industrial electrical consulting',
      summary: 'Specialist advice for factories, industrial sheds and workshops',
      cta: 'Request technical consulting',
      comingSoon: false,
      blocks: [
        { heading: 'Definition', text: 'Specialist consulting in industrial electrical systems for factories, industrial sheds and workshops.' },
        { heading: 'Who it is for', text: 'Technical managers and owners of industrial units.' },
        { heading: 'The Xennic advantage', text: 'Four decades of hands-on experience in distribution networks and industrial power (per FND-001), alongside modern analytical tools.' },
      ],
    },
    {
      slug: 'building-electrical-design',
      title: 'Building electrical design',
      summary: 'Complete design of residential and commercial electrical installations to Mabhas 13',
      cta: 'Request a building electrical design',
      comingSoon: false,
      blocks: [
        { heading: 'Definition', text: 'Complete design of electrical installations for residential and commercial buildings.' },
        { heading: 'Who it is for', text: 'Developers, owners and construction companies.' },
        { heading: 'Scope', text: 'Design to Mabhas 13 of the National Building Regulations and to current technical standards.' },
        { heading: 'The Xennic advantage', text: 'Close adherence to Mabhas 13, combining technical standards with a smart-building approach.' },
      ],
    },
    {
      slug: 'distribution-supervision',
      title: 'Distribution project supervision',
      summary: 'Technical supervision of overhead, underground and substation distribution projects',
      cta: 'Request technical supervision',
      comingSoon: false,
      blocks: [
        { heading: 'Definition', text: 'Technical supervision of distribution network projects (overhead, underground, substation).' },
        { heading: 'Who it is for', text: 'Contractors and electricity distribution companies.' },
        { heading: 'The Xennic advantage', text: 'Real supervision and hand-over experience on medium-voltage networks, plus live-line operational experience (per FND-001, professional record).' },
      ],
    },
    {
      slug: 'energy-audit',
      title: 'Energy audit',
      summary: 'Finding energy losses and optimising consumption in industry and commercial sites',
      cta: 'Request an energy assessment',
      comingSoon: false,
      blocks: [
        { heading: 'Definition', text: 'Industrial energy auditing to identify the causes of losses and optimise consumption.' },
        { heading: 'Who it is for', text: 'High-consumption industries, factories and commercial sites.' },
        { heading: 'The Xennic advantage', text: 'Data-driven analysis of energy consumption, aimed at reducing the client’s real cost.' },
      ],
    },
    {
      slug: 'grounding-lightning-protection',
      title: 'Earthing and lightning protection design',
      summary: 'Design and supervision of earthing systems to IEC standards',
      cta: 'Request earthing and lightning protection design',
      comingSoon: false,
      blocks: [
        { heading: 'Definition', text: 'Design and supervision of earthing and lightning protection systems for tall buildings, industry and data centres.' },
        { heading: 'Who it is for', text: 'Managers of construction and industrial projects with high safety requirements.' },
        { heading: 'The Xennic advantage', text: 'IEC compliance plus real execution experience on comparable projects.' },
      ],
    },
    {
      slug: 'technical-training',
      title: 'Technical training (workshop)',
      summary: 'Specialist courses in live-line work, dispatching and design for engineers and technicians',
      cta: 'Ask when courses start',
      comingSoon: true,
      blocks: [
        { heading: 'Definition', text: 'Specialist training courses in live-line work, dispatching and electrical design.' },
        { heading: 'Who it is for', text: 'Early-career engineers, students and electrical technicians.' },
        { heading: 'The Xennic advantage', text: 'Practical training grounded in real experience rather than theory alone, following the founder’s execution record.' },
      ],
    },
  ],

  trackRecord: [
    { title: 'Live-line maintenance on the Qom overhead network (~10 years)', role: 'Live-line foreman', description: 'Repairs with no supply interruption; ten years without an incident' },
    { title: 'Medium-voltage network hand-over supervision (1392–1398, Persian calendar)', role: 'Hand-over supervisor' },
    { title: 'Installation and repair of 30+ oil/gas 20 kV sectionalizers', role: 'Executor', description: 'Improved network reliability' },
    { title: '10 km of network plus 2 overhead substations (military site, 1395 Persian calendar)', role: 'Project manager' },
    { title: 'Low-voltage 400 V network capacitor installation (400+ cases)', role: 'Executor', description: 'Improved network power factor' },
  ],
} as const

/** The English edition is a static, reviewable list; it is not read from the CMS. */
export type EnglishService = (typeof en.services)[number]

/* ------------------------------------------------------------------------- *
 * View models for the English edition
 * ------------------------------------------------------------------------- */

export function englishServiceCards(): ServiceCardModel[] {
  return en.services.map((service) => ({
    id: service.slug,
    slug: service.slug,
    title: service.title,
    summary: service.summary,
    comingSoon: service.comingSoon,
  }))
}

/**
 * An English service page. The English edition is static, so its body is a
 * plain heading/paragraph list rather than a CMS rich-text document; the rest of
 * the shape matches `ServiceDetailModel` so the same layout can render it.
 */
export type EnglishServiceDetail = {
  slug: string
  title: string
  summary: string
  comingSoon: boolean
  cta: string
  blocks: readonly Block[]
}

export function englishServiceDetail(slug: string): EnglishServiceDetail | null {
  const service = en.services.find((entry) => entry.slug === slug)
  if (!service) return null
  return {
    slug: service.slug,
    title: service.title,
    summary: service.summary,
    comingSoon: service.comingSoon,
    cta: service.cta,
    blocks: service.blocks as unknown as Block[],
  }
}

export function englishTrackRecord(): TrackRecordItemModel[] {
  return en.trackRecord.map((item, index) => ({
    id: `en-${index + 1}`,
    title: item.title,
    role: item.role ?? null,
    description: 'description' in item ? item.description : null,
  }))
}

export function englishTeam(): TeamMemberModel[] {
  return [{ id: 'en-founder', name: en.founderNameLatin, biography: en.founderBio }]
}

/**
 * The English home page. Same sections, same order and the same claims as the
 * Persian home page; only the language and the internal links differ.
 */
export function buildEnglishHomeContent(): HomeContent {
  const base = '/en'
  return {
    hero: {
      eyebrow: 'Electrical, energy and automation engineering',
      title: en.homeTitle,
      summary: en.homeSummary,
      primary: { href: `${base}/contact`, label: 'Request engineering advice' },
      secondary: { href: `${base}/services`, label: 'Explore our services' },
      facts: [
        { value: '4 decades', label: 'Founder’s engineering experience' },
        { value: String(en.services.length), label: 'Specialist service areas' },
        { value: '4 provinces', label: 'Where the founder has worked' },
        { value: 'IEC / Mabhas 13', label: 'Basis for design and supervision' },
      ],
    },
    pillars: en.principles as unknown as Block[],
    services: englishServiceCards().map(({ slug, title, summary, comingSoon }) => ({ slug, title, summary, comingSoon })),
    founder: {
      name: en.founderNameLatin,
      role: 'Founder',
      heading: en.trackRecordIntro.title,
      summary: en.trackRecordIntro.summary,
      text: en.founderBio,
      note: 'This is the founder’s professional record before Xennic existed; it is not a record of company projects.',
    },
    platform: {
      title: 'Xennic Platform',
      badge: 'Coming soon',
      description: 'The Xennic engineering platform is in preparation; more information will be announced with its official release.',
    },
    contact: {
      title: 'Talk to us about the technical review of your project',
      text: 'The official channels (phone, email and messengers) are on the contact page, where you can also send a request.',
      primary: { href: `${base}/contact`, label: 'Contact page' },
      secondary: { href: `${base}/services`, label: 'Browse the services' },
    },
  }
}

/* ------------------------------------------------------------------------- *
 * Section copy for the English tree
 * ------------------------------------------------------------------------- */

/** Sections that are linked but not published yet, with their English titles. */
export const englishNotPublished: Record<string, string> = {
  knowledge: 'Knowledge base',
  tools: 'Engineering tools',
  platform: 'Xennic Platform',
  privacy: 'Privacy',
  terms: 'Terms of use',
  cookies: 'Cookies',
}

/**
 * Title and description for the English sections and for the unpublished
 * placeholders. Written as metadata, not as page copy: every string here is a
 * translation of the Persian entry in the Persian `[section]` page.
 */
export const englishSectionMeta: Record<string, { title: string; description: string }> = {
  company: {
    title: 'About us',
    description: 'Zar-e Noor-e Niroo-e Yekta (Xennic): mission, vision and working principles in power, energy and automation engineering.',
  },
  services: {
    title: 'Services',
    description: 'Industrial electrical consulting, building electrical design, distribution supervision, energy audit, earthing and lightning protection, and technical training.',
  },
  'track-record': {
    title: 'Track record',
    description: 'The hands-on experience of Xennic’s founder in distribution networks and electrical projects, before the company was founded.',
  },
  knowledge: { title: 'Knowledge base', description: 'The Xennic technical knowledge base; in preparation.' },
  tools: { title: 'Engineering tools', description: 'Xennic engineering tools; in preparation.' },
  platform: { title: 'Xennic Platform', description: 'The Xennic engineering platform; in preparation.' },
  privacy: { title: 'Privacy', description: 'The Xennic privacy policy; in preparation.' },
  terms: { title: 'Terms of use', description: 'Terms of use for the Xennic website; in preparation.' },
  cookies: { title: 'Cookies', description: 'The Xennic cookie policy; in preparation.' },
}
