/**
 * A JSON-LD block for the document `<head>`.
 *
 * `JSON.stringify` escapes nothing by itself, so the string is hardened against
 * `</script>` breaking out of the block: `<`, `>` and `&` are written as their
 * JSON unicode escapes. The output is still valid JSON-LD and identical to any
 * crawler that parses it.
 */
export function JsonLd({ data, id }: { data: Record<string, unknown>; id?: string }) {
  const json = JSON.stringify(data)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
  return <script type="application/ld+json" id={id} dangerouslySetInnerHTML={{ __html: json }} />
}
