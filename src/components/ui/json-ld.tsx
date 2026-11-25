/**
 * A JSON-LD block for the document `<head>`.
 *
 * `JSON.stringify` escapes nothing by itself, so the string is hardened against
 * `</script>` breaking out of the block: `<`, `>` and `&` are written as their
 * JSON unicode escapes. The output is still valid JSON-LD and identical to any
 * crawler that parses it.
 */
export function JsonLd({
  data,
  id,
}: {
  /** One node, or a list of nodes placed in a single `@graph`. */
  data: Record<string, unknown> | Record<string, unknown>[]
  id?: string
}) {
  const graph = Array.isArray(data) ? { '@context': 'https://schema.org', '@graph': data } : data
  const json = JSON.stringify(graph)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
  return <script type="application/ld+json" id={id} dangerouslySetInnerHTML={{ __html: json }} />
}
