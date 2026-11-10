'use server'

/**
 * Server action behind the public contact form.
 *
 * The public site has no write access to the `lead-submissions` collection:
 * anonymous REST writes stay 403. The action validates input, applies a simple
 * per-address rate limit and only then creates the lead with `overrideAccess`.
 * A success state is returned strictly after the record exists — never before.
 */
import { headers } from 'next/headers'
import { getPayload } from 'payload'
import config from '@payload-config'
import { z } from 'zod'
import type { ContactFormState } from './contact-form'

const WINDOW_MS = 10 * 60 * 1000
const MAX_SUBMISSIONS = 5
const submissions = new Map<string, number[]>()

function rateLimited(key: string, now: number): boolean {
  const recent = (submissions.get(key) ?? []).filter((time) => now - time < WINDOW_MS)
  if (recent.length >= MAX_SUBMISSIONS) {
    submissions.set(key, recent)
    return true
  }
  recent.push(now)
  submissions.set(key, recent)
  if (submissions.size > 5000) submissions.clear()
  return false
}

const payloadSchema = z
  .object({
    name: z.string().trim().min(2, 'نام را کامل‌تر وارد کنید.').max(120, 'نام بیش از حد بلند است.'),
    phone: z.string().trim().max(40, 'شمارهٔ تماس بیش از حد بلند است.').default(''),
    email: z.string().trim().max(160, 'رایانامه بیش از حد بلند است.').default(''),
    subject: z.string().trim().max(160, 'موضوع بیش از حد بلند است.').default(''),
    message: z
      .string()
      .trim()
      .min(10, 'متن پیام را کامل‌تر بنویسید (حداقل ۱۰ نویسه).')
      .max(4000, 'متن پیام بیش از حد بلند است.'),
  })
  .superRefine((value, ctx) => {
    if (value.email && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value.email)) {
      ctx.addIssue({ code: 'custom', path: ['email'], message: 'قالب رایانامه درست نیست.' })
    }
    if (value.phone && !/^[0-9\u06F0-\u06F9+\-()\s]{6,}$/.test(value.phone)) {
      ctx.addIssue({ code: 'custom', path: ['phone'], message: 'شمارهٔ تماس فقط می‌تواند رقم و علامت‌های رایج داشته باشد.' })
    }
    if (!value.phone && !value.email) {
      ctx.addIssue({
        code: 'custom',
        path: ['phone'],
        message: 'برای پاسخ، شمارهٔ تماس یا رایانامه را وارد کنید.',
      })
    }
  })

function clientAddress(headerBag: Headers): string {
  const forwarded = headerBag.get('x-forwarded-for')
  if (forwarded) return forwarded.split(',')[0].trim() || 'unknown'
  return headerBag.get('x-real-ip')?.trim() || 'unknown'
}

export async function submitContact(
  _previous: ContactFormState,
  formData: FormData,
): Promise<ContactFormState> {
  const honeypot = String(formData.get('company') ?? '').trim()
  if (honeypot) {
    return { status: 'error', message: 'درخواست نامعتبر است و ثبت نشد.' }
  }

  const parsed = payloadSchema.safeParse({
    name: String(formData.get('name') ?? ''),
    phone: String(formData.get('phone') ?? ''),
    email: String(formData.get('email') ?? ''),
    subject: String(formData.get('subject') ?? ''),
    message: String(formData.get('message') ?? ''),
  })

  if (!parsed.success) {
    const errors: Record<string, string> = {}
    for (const issue of parsed.error.issues) {
      const field = typeof issue.path[0] === 'string' ? issue.path[0] : 'form'
      if (!errors[field]) errors[field] = issue.message
    }
    return { status: 'error', message: 'برخی از فیلدها نیاز به اصلاح دارند.', errors }
  }

  const headerBag = await headers()
  if (rateLimited(clientAddress(headerBag), Date.now())) {
    return {
      status: 'error',
      message: 'تعداد پیام‌های ارسالی از این نشانی زیاد بوده است؛ چند دقیقه بعد دوباره تلاش کنید.',
    }
  }

  const data = parsed.data
  try {
    const payload = await getPayload({ config })
    await payload.create({
      collection: 'lead-submissions',
      data: {
        name: data.name,
        phone: data.phone || undefined,
        email: data.email || undefined,
        subject: data.subject || 'درخواست تماس از وب‌سایت',
        message: data.message,
        source: 'website-contact',
        status: 'new',
      },
      // The collection itself stays staff-only for every public API call.
      overrideAccess: true,
    })
  } catch (error) {
    // Log the failure type only; the message itself is private correspondence.
    console.error('contact submission failed:', error instanceof Error ? error.name : 'unknown error')
    return {
      status: 'error',
      message: 'ثبت پیام در سامانه انجام نشد. لطفاً از تلفن یا رایانامهٔ رسمی استفاده کنید.',
    }
  }

  return {
    status: 'success',
    message: 'پیام شما در سامانهٔ Xennic ثبت شد. برای پاسخ سریع‌تر می‌توانید تلفنی هم تماس بگیرید.',
  }
}
