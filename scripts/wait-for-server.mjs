const target = process.env.TEST_BASE_URL || 'http://127.0.0.1:3000'
const deadline = Date.now() + 120_000
while (Date.now() < deadline) {
  try {
    const response = await fetch(target, { signal: AbortSignal.timeout(5_000) })
    if (response.ok) {
      console.log('Development server is ready.')
      process.exit(0)
    }
  } catch {
    // The development server may still be starting or compiling.
  }
  await new Promise(resolve => setTimeout(resolve, 1_000))
}
console.error('Development server did not become ready within 120 seconds.')
process.exit(1)
