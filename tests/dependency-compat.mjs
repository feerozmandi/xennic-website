import assert from 'node:assert/strict'
import { test } from 'node:test'
import { DateTimeResolver, EmailAddressResolver } from 'graphql-scalars'
import { createHeadlessEditor } from '@lexical/headless'
import { withDOM } from '@lexical/headless/dom'
import { $generateNodesFromDOM } from '@lexical/html'
import { $getRoot } from 'lexical'

test('Payload GraphQL scalar imports handle dates and email', () => {
  assert.equal(new Date(DateTimeResolver.serialize('2026-10-29T00:00:00Z')).toISOString(), '2026-10-29T00:00:00.000Z')
  assert.equal(EmailAddressResolver.serialize('test@example.invalid'), 'test@example.invalid')
  assert.throws(() => EmailAddressResolver.serialize('not-an-email'))
})

test('Lexical headless HTML import works with the overridden DOM dependency', () => {
  const editor = createHeadlessEditor({ nodes: [], onError(error) { throw error } })
  withDOM((window) => {
    const document = new window.DOMParser().parseFromString('<p>Sample <strong>text</strong></p>', 'text/html')
    editor.update(() => {
      $getRoot().clear().append(...$generateNodesFromDOM(editor, document))
    }, { discrete: true })
  })
  assert.equal(editor.getEditorState().read(() => $getRoot().getTextContent()), 'Sample text')
})
