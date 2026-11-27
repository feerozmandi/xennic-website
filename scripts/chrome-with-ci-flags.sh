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
set -euo pipefail

REAL_CHROME="${DECLARE_REAL_CHROME:?the real browser's path is required}"
if [ ! -x "$REAL_CHROME" ]; then
  echo "chrome-with-ci-flags: $REAL_CHROME is not an executable" >&2
  exit 2
fi

exec "$REAL_CHROME" \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  "$@"
