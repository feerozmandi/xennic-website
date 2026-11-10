/**
 * Content contract between the CMS layer and the website UI.
 * Components receive plain, typed data; they never import Payload.
 */

export type Block = { heading: string; text: string }

export type HomeService = {
  slug: string
  title: string
  summary: string
  comingSoon: boolean
}

export type HomeFact = { value: string; label: string }

export type HomeContent = {
  hero: {
    eyebrow: string
    title: string
    summary: string
    primary: { href: string; label: string }
    secondary: { href: string; label: string }
    facts: HomeFact[]
  }
  pillars: Block[]
  services: HomeService[]
  founder: { name: string; role: string; heading: string; summary: string; text: string; note: string }
  platform: { title: string; badge: string; description: string }
  contact: { title: string; text: string; primary: { href: string; label: string }; secondary: { href: string; label: string } }
}

type LexicalNode = {
  type?: string
  tag?: string
  text?: string
  children?: LexicalNode[]
}

/** Flatten the approved rich-text blocks into heading/paragraph pairs. */
export function extractBlocks(content: unknown): Block[] {
  const root = (content as { root?: LexicalNode } | null | undefined)?.root
  if (!root?.children) return []
  const text = (node: LexicalNode): string =>
    node.text ?? (node.children ?? []).map(text).join('')
  const blocks: Block[] = []
  let pending: string | null = null
  for (const node of root.children) {
    if (node.type === 'heading') {
      pending = text(node)
    } else if (node.type === 'paragraph') {
      const value = text(node)
      if (pending) blocks.push({ heading: pending, text: value })
      else blocks.push({ heading: '', text: value })
      pending = null
    }
  }
  return blocks
}

export const FOUNDER_NAME = 'احمد فیروزمندی'

/** Locale-independent Persian digits (keeps server and client markup identical). */
export function faNumber(value: number): string {
  return String(value).replace(/[0-9]/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'[Number(digit)])
}

/** Approved public copy (L2-MKT-004) expressed for the redesigned layout. */
export function buildHomeContent(input: {
  pageTitle?: string
  pageSummary?: string
  blocks: Block[]
  aboutBlocks?: Block[]
  services: HomeService[]
  trackRecord?: { heading?: string; summary?: string }
}): HomeContent {
  const founderBlock = (input.aboutBlocks ?? []).find((block) => block.heading.includes('مؤسس'))
  const pillars = input.blocks.filter((block) => block.heading)
  return {
    hero: {
      eyebrow: 'مهندسی برق، انرژی و اتوماسیون',
      title: input.pageTitle ?? 'مهندسی انرژی برای تصمیم‌های دقیق‌تر و آینده‌ای هوشمندتر',
      summary: input.pageSummary ?? '',
      primary: { href: '/contact', label: 'درخواست مشاورهٔ مهندسی' },
      secondary: { href: '/services', label: 'آشنایی با خدمات' },
      facts: [
        { value: '۴ دهه', label: 'تجربهٔ مهندسی مؤسس' },
        { value: faNumber(input.services.length), label: 'حوزهٔ خدمت تخصصی' },
        { value: '۴ استان', label: 'سابقهٔ فعالیت' },
        { value: 'IEC / مبحث ۱۳', label: 'مبنای طراحی و نظارت' },
      ],
    },
    pillars,
    services: input.services,
    founder: {
      name: FOUNDER_NAME,
      role: 'مؤسس',
      heading: input.trackRecord?.heading ?? 'تجربهٔ مهندسی که می‌توان به آن اعتماد کرد',
      summary: input.trackRecord?.summary ?? '',
      text: founderBlock?.text ?? '',
      note: 'این پیشینه، سابقهٔ حرفه‌ای مؤسس پیش از تأسیس Xennic است و به‌معنای سابقهٔ پروژه‌های شرکت نیست.',
    },
    platform: {
      title: 'Xennic Platform',
      badge: 'به‌زودی',
      description: 'پلتفرم مهندسی Xennic در حال آماده‌سازی است؛ اطلاعات بیشتر پس از انتشار رسمی اعلام می‌شود.',
    },
    contact: {
      title: 'برای بررسی فنی پروژهٔ خود با ما گفت‌وگو کنید',
      text: 'مسیرهای تماس رسمی (تلفن، رایانامه و پیام‌رسان‌ها) در صفحهٔ تماس آمده است؛ همان‌جا می‌توانید درخواست خود را ثبت کنید.',
      primary: { href: '/contact', label: 'صفحهٔ تماس' },
      secondary: { href: '/services', label: 'مرور خدمات' },
    },
  }
}
