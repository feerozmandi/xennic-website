import { getPayload } from 'payload'
import config from '../src/payload.config'
import type { Page, Service } from '../src/payload-types'

// Verbatim public copy from L2-MKT-004 v0.2.0, Vault dev cd38e4b.
// The five principles below are explicitly incorporated by reference to L2-MKT-002 §9.
type Block = { heading: string; text: string }
function richText(blocks: Block[]): NonNullable<Page['content']> {
  return {
    root: {
      type: 'root', direction: 'rtl', format: '', indent: 0, version: 1,
      children: blocks.flatMap(({ heading, text }) => [
        { type: 'heading', tag: 'h2', direction: 'rtl', format: '', indent: 0, version: 1, children: [{ type: 'text', text: heading, detail: 0, format: 0, mode: 'normal', style: '', version: 1 }] },
        { type: 'paragraph', direction: 'rtl', format: '', indent: 0, version: 1, textFormat: 0, textStyle: '', children: [{ type: 'text', text, detail: 0, format: 0, mode: 'normal', style: '', version: 1 }] },
      ]),
    },
  }
}

const founder = 'احمد فیروزمندی — مهندس برق قدرت با نزدیک به ۴ دهه تجربهٔ عملی در صنعت برق ایران؛ متخصص شبکهٔ توزیع، خط گرم (Live Line)، دیسپاچینگ و طراحی تأسیسات برق صنعتی و ساختمانی. عضو سازمان نظام مهندسی استان قم. سابقهٔ فعالیت در قم، تهران، مازندران و اصفهان. در کنار تجربهٔ مهندسی، بنیان‌گذار و توسعه‌دهندهٔ فروشگاه آنلاین «سالنمای نو» (salenoo.ir) و فعال در حوزهٔ هوش مصنوعی و اتوماسیون فرایندها — همین پیشینه، پایهٔ تلفیق «مهندسی سنتی + فناوری هوشمند» را شکل داده که مأموریت Xennic بر آن استوار است.'
const pages: Array<Pick<Page, 'title' | 'slug' | 'summary' | 'content'>> = [
  {
    slug: 'home', title: 'مهندسی انرژی برای تصمیم‌های دقیق‌تر و آینده‌ای هوشمندتر',
    summary: 'زر نور نیرو یکتا در حوزهٔ مهندسی برق، انرژی و انرژی‌های تجدیدپذیر، راهکارهای مهندسی، مشاوره و تحلیل تخصصی ارائه می‌دهد؛ با تکیه بر دانش مهندسی و فناوری‌های نوین.',
    content: richText([
      { heading: 'Engineering First', text: 'تصمیم‌ها بر اساس اصول و استانداردهای مهندسی' },
      { heading: 'Evidence Based', text: 'نتایج مبتنی بر داده، منابع و شواهد' },
      { heading: 'Technology Enabled', text: 'استفاده از نرم‌افزار، AI و ابزارهای دیجیتال' },
      { heading: 'Independent Thinking', text: 'تمرکز بر تحلیل و راهکار، نه صرفاً فروش محصول' },
      { heading: 'Long-Term Perspective', text: 'راهکارهایی با نگاه بلندمدت به انرژی و زیرساخت' },
    ]),
  },
  {
    slug: 'about', title: 'درباره ما', content: richText([
      { heading: 'مأموریت', text: 'شرکت زر نور نیرو یکتا (برند تجاری: Xennic) با اتکا بر دانش مهندسی، تخصص حرفه‌ای و نوآوری مستمر، راهکارهای جامع مشاوره، طراحی، نظارت و اجرا در حوزهٔ مهندسی برق قدرت، اتوماسیون و انرژی‌های تجدیدپذیر ارائه می‌دهد.' },
      { heading: 'چشم‌انداز', text: 'در افق بلندمدت، زر نور نیرو یکتا به یکی از مراجع معتبر ارائهٔ خدمات مهندسی برق و انرژی در ایران تبدیل می‌شود؛ جایی که نام شرکت مترادف با اعتماد، دانش، کیفیت و نوآوری مهندسی است.' },
      { heading: 'مهندسی هوشمند', text: 'تلفیق دانش مهندسی با فناوری و هوش مصنوعی' },
      { heading: 'کیفیت', text: 'تعهد به دقت و استاندارد در تمام خدمات' },
      { heading: 'اعتماد', text: 'صداقت و شفافیت در تعامل با مشتری' },
      { heading: 'آینده‌نگری', text: 'راهکارهایی با نگاه بلندمدت به انرژی و زیرساخت' },
      { heading: 'یادگیری مستمر', text: 'به‌روزرسانی دائمی دانش فنی طبق آخرین استانداردها' },
      { heading: 'دربارهٔ مؤسس', text: founder },
    ]),
  },
]
const services: Array<Pick<Service, 'title' | 'slug' | 'summary' | 'content' | 'cta' | 'comingSoon'>> = [
  { slug: 'industrial-electrical-consulting', title: 'مشاورهٔ فنی برق صنعتی', summary: 'مشاورهٔ تخصصی برای کارخانجات، سوله‌ها و کارگاه‌های صنعتی', cta: 'درخواست مشاورهٔ فنی', content: richText([
    { heading: 'تعریف', text: 'مشاورهٔ تخصصی در حوزهٔ برق صنعتی برای کارخانجات، سوله‌ها و کارگاه‌ها.' },
    { heading: 'مخاطب هدف', text: 'مدیران فنی و صاحبان واحدهای صنعتی.' },
    { heading: 'مزیت Xennic', text: 'چهار دهه تجربهٔ عملی در شبکهٔ توزیع و برق صنعتی (طبق FND-001)، همراه با ابزارهای تحلیلی نوین.' },
  ]) },
  { slug: 'building-electrical-design', title: 'طراحی برق ساختمان', summary: 'طراحی کامل تأسیسات برقی مسکونی و تجاری مطابق مبحث ۱۳', cta: 'درخواست طراحی برق ساختمان', content: richText([
    { heading: 'تعریف', text: 'طراحی کامل تأسیسات برقی ساختمان‌های مسکونی و تجاری.' },
    { heading: 'مخاطب هدف', text: 'سازندگان، مالکان و شرکت‌های ساختمانی.' },
    { heading: 'دامنهٔ خدمت', text: 'طراحی مطابق مبحث ۱۳ مقررات ملی ساختمان و استانداردهای فنی روز.' },
    { heading: 'مزیت Xennic', text: 'رعایت دقیق مبحث ۱۳، تلفیق استانداردهای فنی با رویکرد هوشمندسازی.' },
  ]) },
  { slug: 'distribution-supervision', title: 'نظارت بر پروژه‌های توزیع', summary: 'نظارت فنی بر پروژه‌های شبکهٔ توزیع هوایی، زمینی و پست', cta: 'درخواست نظارت فنی', content: richText([
    { heading: 'تعریف', text: 'نظارت فنی بر پروژه‌های شبکهٔ توزیع (هوایی، زمینی، پست).' },
    { heading: 'مخاطب هدف', text: 'پیمانکاران و شرکت‌های توزیع برق.' },
    { heading: 'مزیت Xennic', text: 'سابقهٔ واقعی نظارت و تحویل در شبکهٔ فشار متوسط و تجربهٔ عملیاتی خط گرم (طبق FND-001، بخش سوابق شغلی).' },
  ]) },
  { slug: 'energy-audit', title: 'ممیزی انرژی', summary: 'شناسایی اتلاف انرژی و بهینه‌سازی مصرف صنایع و مراکز تجاری', cta: 'درخواست ارزیابی انرژی', content: richText([
    { heading: 'تعریف', text: 'ممیزی انرژی صنایع برای شناسایی عوامل اتلاف و بهینه‌سازی مصرف.' },
    { heading: 'مخاطب هدف', text: 'صنایع، کارخانجات و مراکز تجاری پرمصرف.' },
    { heading: 'مزیت Xennic', text: 'تحلیل داده‌محور مصرف انرژی، با هدف کاهش هزینهٔ واقعی مشتری.' },
  ]) },
  { slug: 'grounding-lightning-protection', title: 'طراحی سیستم ارت و صاعقه‌گیر', summary: 'طراحی و نظارت سیستم‌های ارتینگ طبق استاندارد IEC', cta: 'درخواست طراحی ارت و صاعقه‌گیر', content: richText([
    { heading: 'تعریف', text: 'طراحی و نظارت سیستم ارتینگ و صاعقه‌گیر برای ساختمان‌های بلند، صنایع و مراکز داده.' },
    { heading: 'مخاطب هدف', text: 'مدیران پروژه‌های ساختمانی و صنعتی با الزامات ایمنی بالا.' },
    { heading: 'مزیت Xennic', text: 'رعایت استاندارد IEC و تجربهٔ اجرایی واقعی در پروژه‌های مشابه.' },
  ]) },
  { slug: 'technical-training', title: 'آموزش فنی (کارگاه)', summary: 'دوره‌های تخصصی خط گرم، دیسپاچینگ و طراحی برای مهندسان و تکنسین‌ها', cta: 'اطلاع از زمان شروع دوره‌ها', comingSoon: true, content: richText([
    { heading: 'تعریف', text: 'دوره‌های آموزشی تخصصی در حوزهٔ خط گرم، دیسپاچینگ و طراحی برق.' },
    { heading: 'مخاطب هدف', text: 'مهندسان جوان، دانشجویان و تکنسین‌های برق.' },
    { heading: 'مزیت Xennic', text: 'آموزش عملی مبتنی بر تجربهٔ واقعی (نه فقط تئوری)، طبق سابقهٔ اجرایی مؤسس.' },
  ]) },
]
const trackRecord = [
  { title: 'تعمیرات خط گرم شبکهٔ هوایی استان قم (~۱۰ سال)', role: 'استادکار خط گرم', description: 'تعمیرات بدون قطعی برق، ۱۰ سال بدون حادثه' },
  { title: 'نظارت تحویل و تحول شبکهٔ فشار متوسط (۱۳۹۲-۱۳۹۸)', role: 'ناظر تحویل' },
  { title: 'نصب و تعمیر ۳۰+ سکسیونر روغنی/گازی ۲۰kV', role: 'مجری', description: 'بهبود قابلیت اطمینان شبکه' },
  { title: '۱۰ کیلومتر شبکه + ۲ پست هوایی (مکان نظامی، ۱۳۹۵)', role: 'مدیر پروژه' },
  { title: 'خازن‌گذاری شبکهٔ فشار ضعیف ۴۰۰ ولت (۴۰۰+ مورد)', role: 'مجری', description: 'بهبود ضریب توان شبکه' },
]

async function main() {
  const payload = await getPayload({ config })
  try {
    for (const page of pages) {
      const existing = await payload.find({ collection: 'pages', where: { slug: { equals: page.slug } }, limit: 1 })
      if (!existing.totalDocs) await payload.create({ collection: 'pages', data: page })
    }
    for (const service of services) {
      const existing = await payload.find({ collection: 'services', where: { slug: { equals: service.slug } }, limit: 1 })
      if (!existing.totalDocs) await payload.create({ collection: 'services', data: service })
    }
    for (const item of trackRecord) {
      const existing = await payload.find({ collection: 'track-record-items', where: { title: { equals: item.title } }, limit: 1 })
      if (!existing.totalDocs) await payload.create({ collection: 'track-record-items', data: item })
    }
    const existing = await payload.find({ collection: 'team-members', where: { name: { equals: 'احمد فیروزمندی' } }, limit: 1 })
    if (!existing.totalDocs) await payload.create({ collection: 'team-members', data: { name: 'احمد فیروزمندی', biography: founder } })
    console.log('Approved seed complete. Existing records were not overwritten.')
  } finally {
    await payload.destroy()
  }
}

// Payload's PostgreSQL adapter retains a client; explicitly exit after completed writes.
main().then(() => process.exit(0)).catch((error: unknown) => { console.error('Seed failed:', error); process.exit(1) })
