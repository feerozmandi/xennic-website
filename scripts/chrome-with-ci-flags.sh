#!/usr/bin/env bash
# A Chrome to drive, with the flags a CI runner needs.
#
#   chrome-with-ci-flags --version
#
# WHY THIS EXISTS. The Declare toolchain launches Chrome itself, and the
# flags it passes are the ones a developer's own machine needs. On a CI
# runner the browser runs inside a container, where two of them matter:
#
#   --no-sandbox            the runner's user is not allowed the sandbox
#                           Chrome wants, and without the flag Chrome does
#                           not start at all
#   --disable-dev-shm-usage the runner's /dev/shm is small, and Chrome uses
#                           it for shared memory; without the flag the
#                           browser dies mid-run, taking the process that
#                           was driving it with it
#
# The toolchain takes the browser's path from `CHROME_PATH` and runs it as
# it is, so this puts a browser at that path that adds the flags and then
# hands everything else over untouched.
#
# WHAT IT ALSO KEEPS. The toolchain starts the browser with its own
# output thrown away, so a browser that refuses to start says nothing at
# all -- the run reports only that the browser did not start. This copies
# what the browser says into the file named by `DECLARE_CHROME_LOG`, and
# still passes it on, so a browser's own words are kept.
#
# A NOTE ON THE WORDING. An apostrophe inside "${VAR:?...}" opens a
# quoted string that nothing closes, and bash then refuses to parse the
# whole file: the wrapper never runs, the browser never starts, and the
# toolchain reports only that a kept Chrome did not start. So the wording
# below has no apostrophes in it, and the file is checked with `bash -n`
# before it is used.
set -euo pipefail

if [ -z "${DECLARE_REAL_CHROME:-}" ]; then
  echo "chrome-with-ci-flags: DECLARE_REAL_CHROME is required" >&2
  exit 2
fi
REAL_CHROME="$DECLARE_REAL_CHROME"
CHROME_LOG="${DECLARE_CHROME_LOG:-}"

if [ ! -x "$REAL_CHROME" ]; then
  echo "chrome-with-ci-flags: $REAL_CHROME is not an executable" >&2
  if [ -n "$CHROME_LOG" ]; then
    echo "chrome-with-ci-flags: $REAL_CHROME is not an executable" >> "$CHROME_LOG"
  fi
  exit 2
fi

if [ -n "$CHROME_LOG" ]; then
  {
    echo "-- chrome-with-ci-flags at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "-- the browser: $REAL_CHROME"
    echo "-- its version: $("$REAL_CHROME" --version 2>/dev/null || echo 'it would not say')"
    echo "-- the flags it is given:"
    printf '   %s\n' "$@"
  } >> "$CHROME_LOG" 2>&1 || true
  # The browser's own words are copied to the log and still passed on: the
  # toolchain reads the browser's address from that same stream.
  exec "$REAL_CHROME" \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    "$@" 2> >(tee -a "$CHROME_LOG" >&2)
else
  exec "$REAL_CHROME" \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    "$@"
fi
