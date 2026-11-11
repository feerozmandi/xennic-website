'use client'

/**
 * Public contact form.
 *
 * The success state is rendered only after the server action reports that the
 * record exists. There is no optimistic success, no timer and no fake receipt.
 *
 * The language is a hidden field: the action answers in the same language the
 * visitor is reading, so a validation message never switches language halfway
 * through the form.
 */
import { useActionState, useEffect, useRef } from 'react'
import { submitContact } from '@/lib/contact-actions'
import { INITIAL_CONTACT_STATE } from '@/lib/contact-form'
import { getDictionary, type Locale } from '@/lib/i18n'

export function ContactForm({ locale = 'fa' }: { locale?: Locale }) {
  const dict = getDictionary(locale)
  const [state, formAction, isPending] = useActionState(submitContact, INITIAL_CONTACT_STATE)
  const statusRef = useRef<HTMLDivElement>(null)
  const errors = state.errors ?? {}
  const hasErrors = Object.keys(errors).length > 0
  const labels = dict.form

  const fields = [
    { name: 'name', label: labels.name, type: 'text', required: true, autoComplete: 'name' },
    { name: 'phone', label: labels.phone, type: 'tel', required: false, autoComplete: 'tel' },
    { name: 'email', label: labels.email, type: 'email', required: false, autoComplete: 'email' },
    { name: 'subject', label: labels.subject, type: 'text', required: false, autoComplete: 'off' },
  ] as const

  useEffect(() => {
    if (state.status !== 'idle') statusRef.current?.focus()
  }, [state])

  if (state.status === 'success') {
    return (
      <div className="form-success" role="status" tabIndex={-1} ref={statusRef}>
        <h3 className="h3">{labels.successTitle}</h3>
        <p>{state.message}</p>
        <p className="form-note">{labels.successHint}</p>
      </div>
    )
  }

  return (
    <form action={formAction} className="contact-form" aria-labelledby="contact-form-title">
      <h3 id="contact-form-title" className="h3">{labels.title}</h3>
      <p className="form-note">{labels.note}</p>
      <input type="hidden" name="locale" value={locale} />

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

      {fields.map((field) => {
        const id = `contact-${field.name}`
        const error = errors[field.name]
        return (
          <div className="field" key={field.name}>
            <label htmlFor={id}>
              {field.label}
              {field.required ? <span aria-hidden="true"> *</span> : <span className="field__optional"> {labels.optional}</span>}
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
          {labels.message}<span aria-hidden="true"> *</span>
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
        <label htmlFor="contact-company">{labels.company}</label>
        <input id="contact-company" name="company" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <div className="form-actions">
        <button type="submit" className="button" disabled={isPending}>
          {isPending ? labels.sending : labels.submit}
        </button>
        <span className="form-note">{labels.requiredNote}</span>
      </div>
    </form>
  )
}
