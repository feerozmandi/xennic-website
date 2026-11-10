/**
 * Shared contact-form contract.
 *
 * Kept out of the `'use server'` module: such modules may only export async
 * functions, so constants and types live here and are imported by both the
 * server action and the client component.
 */
export type ContactFormState = {
  status: 'idle' | 'success' | 'error'
  message: string
  /** Field-level messages keyed by input name. */
  errors?: Record<string, string>
}

export const INITIAL_CONTACT_STATE: ContactFormState = { status: 'idle', message: '' }
