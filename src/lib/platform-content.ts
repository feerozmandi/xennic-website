/**
 * What the platform page says about its three tools, in both languages.
 *
 * This is the copy *around* the Declare island, not inside it: the island's own
 * Persian text lives in the Declare program
 * (`declare-apps/xennic-platform/`), and this file explains the tools to a
 * reader before it loads and to a crawler that never will.
 *
 * Nothing here states a project, a client or a saving. Each entry names a
 * method, the inputs it takes and the limits of its answer — the same three
 * facts the island states in its own panels.
 */
import type { Locale } from './i18n'

export type PlatformTool = {
  title: string
  detail: string
  inputs: string
}

const TOOLS: Record<Locale, PlatformTool[]> = {
  fa: [
    {
      title: 'محاسبه‌گر بانک خازنی ۴۰۰ ولت',
      detail:
        'ظرفیت لازم بانک خازنی را از توان اکتیو و ضریب توان فعلی و هدف حساب می‌کند، پله‌بندی را به پلهٔ انتخابی شما گرد می‌کند و کاهش جریان خط را نشان می‌دهد.',
      inputs: 'توان اکتیو (kW)، ضریب توان فعلی و هدف، اندازهٔ پله (kVAr)',
    },
    {
      title: 'تخمین‌گر نیروگاه خورشیدی',
      detail:
        'از مساحت سقف یا دیماند مصرفی و استان پروژه، ظرفیت قابل نصب، تعداد پنل و تولید سالانه را تخمین می‌زند؛ محدودکننده (سقف یا دیماند) را نام می‌برد.',
      inputs: 'مساحت سقف (m²)، دیماند (kW)، استان، نسبت کارکرد',
    },
    {
      title: 'ارزیاب ممیزی انرژی و ارتینگ',
      detail:
        'شش نشانهٔ رایج اتلاف و ریسک را می‌پرسد و پاسخ‌ها را به یک فهرست اولویت کوتاه تبدیل می‌کند، تا معلوم شود بررسی میدانی از کجا باید شروع شود.',
      inputs: 'شش پرسش بله/خیر دربارهٔ اندازه‌گیری، ضریب توان، روشنایی، موتورها، ارتینگ و تعرفه',
    },
  ],
  en: [
    {
      title: '400 V capacitor bank calculator',
      detail:
        'Sizes the reactive power a bank has to supply from active power and the present and target power factor, rounds it to the step you choose, and shows the line current that comes off.',
      inputs: 'Active power (kW), present and target power factor, step size (kVAr)',
    },
    {
      title: 'Solar plant estimator',
      detail:
        'From roof area or site demand and the province, estimates installable capacity, module count and annual yield — and names which of the two limits bound it.',
      inputs: 'Roof area (m²), demand (kW), province, performance ratio',
    },
    {
      title: 'Energy audit and earthing triage',
      detail:
        'Asks six common signs of loss and risk and sorts the answers into a short priority list, so a site visit starts where it matters.',
      inputs: 'Six yes/no facts about metering, power factor, lighting, motors, earthing and tariff',
    },
  ],
}

export function platformTools(locale: Locale): readonly PlatformTool[] {
  return TOOLS[locale]
}
