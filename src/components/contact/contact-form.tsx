'use client'

/**
 * Public contact form.
 *
 * The success state is rendered only after the server action reports that the
 * record exists. There is no optimistic success, no timer and no fake receipt.
 */
import { useActionState, useEffect, useRef } from 'react'
import { submitContact } from '@/lib/contact-actions'
import { INITIAL_CONTACT_STATE } from '@/lib/contact-form'

const FIELDS = [
  { name: 'name', label: 'نام و نام خانوادگی', type: 'text', required: true, autoComplete: 'name' },
  { name: 'phone', label: 'شمارهٔ تماس', type: 'tel', required: false, autoComplete: 'tel' },
  { name: 'email', label: 'رایانامه', type: 'email', required: false, autoComplete: 'email' },
  { name: 'subject', label: 'موضوع', type: 'text', required: false, autoComplete: 'off' },
] as const

export function ContactForm() {
  const [state, formAction, isPending] = useActionState(submitContact, INITIAL_CONTACT_STATE)
  const statusRef = useRef<HTMLDivElement>(null)
  const errors = state.errors ?? {}
  const hasErrors = Object.keys(errors).length > 0

  useEffect(() => {
    if (state.status !== 'idle') statusRef.current?.focus()
  }, [state])

  if (state.status === 'success') {
    return (
      <div className="form-success" role="status" tabIndex={-1} ref={statusRef}>
        <h3 className="h3">پیام ثبت شد</h3>
        <p>{state.message}</p>
        <p className="form-note">
          اگر پاسخ فوری لازم دارید، از شمارهٔ تلفن یا پیام‌رسان‌های همین صفحه استفاده کنید.
        </p>
      </div>
    )
  }

  return (
    <form action={formAction} className="contact-form" aria-labelledby="contact-form-title">
      <h3 id="contact-form-title" className="h3">فرم درخواست تماس</h3>
      <p className="form-note">
        پیام شما در سامانهٔ داخلی Xennic ثبت می‌شود. برای پاسخ سریع‌تر، شمارهٔ تماس یا رایانامه را وارد کنید.
      </p>

      <div ref={statusRef} tabIndex={-1} className="form-status" aria-live="polite">
        {state.status === 'error' && (
          <div role="alert" className="form-alert">
            <p>{state.message}</p>
            {hasErrors && (
              <ul>
                {Object.entries(errors).map(([field, message]) => (
                  <li key={field}>
                    <a href={`#contact-${field}`}>{message}</a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {FIELDS.map((field) => {
        const id = `contact-${field.name}`
        const error = errors[field.name]
        return (
          <div className="field" key={field.name}>
            <label htmlFor={id}>
              {field.label}
              {field.required ? <span aria-hidden="true"> *</span> : <span className="field__optional"> (اختیاری)</span>}
            </label>
            <input
              id={id}
              name={field.name}
              type={field.type}
              required={field.required}
              autoComplete={field.autoComplete}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-error` : undefined}
              dir={field.type === 'email' || field.type === 'tel' ? 'ltr' : undefined}
            />
            {error && (
              <p className="field__error" id={`${id}-error`}>
                {error}
              </p>
            )}
          </div>
        )
      })}

      <div className="field">
        <label htmlFor="contact-message">
          متن پیام<span aria-hidden="true"> *</span>
        </label>
        <textarea
          id="contact-message"
          name="message"
          rows={6}
          required
          aria-invalid={errors.message ? true : undefined}
          aria-describedby={errors.message ? 'contact-message-error' : undefined}
        />
        {errors.message && (
          <p className="field__error" id="contact-message-error">
            {errors.message}
          </p>
        )}
      </div>

      {/* Honeypot: hidden from people and assistive technology, never focusable. */}
      <div className="hp-field" aria-hidden="true">
        <label htmlFor="contact-company">شرکت</label>
        <input id="contact-company" name="company" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <div className="form-actions">
        <button type="submit" className="button" disabled={isPending}>
          {isPending ? 'در حال ارسال…' : 'ارسال پیام'}
        </button>
        <span className="form-note">برای ارسال، هر دو فیلد ستاره‌دار الزامی است.</span>
      </div>
    </form>
  )
}
