#!/usr/bin/env bash
# Verify the Declare program: the toolchain's own ladder, and the bundle the
# site publishes.
#
#   ./scripts/declare-verify.sh
#
# WHAT IT DOES, IN TWO HALVES.
#
# 1. The ladder. `declare-verify` climbs the toolchain's verifiability ladder
#    over the program's source: it parses it, resolves every name, typechecks
#    it, and boots it (in a browser when there is one, so the text is
#    measured for real; headless otherwise, where a stand-in measures it).
#    This is the check the Declare build never had in CI.
#
# 2. The bundle. The site's `/platform` page asks for one exact file name,
#    `app.<hash>.js`, and a stale or hand-edited bundle is a 404 on a page
#    that otherwise looks fine. So the program is rebuilt here, with the
#    pinned toolchain, and the result is compared with the bundle committed in
#    the repository. Byte for byte: the same source and the same compiler
#    give the same program.
#
# WHY THE TOOLCHAIN IS FETCHED, NOT VENDORED. It is a compiler the site
# itself never runs — `npm ci` in the website must not fetch a compiler it
# never runs — so it is taken from the commit recorded in the program's
# `toolchain.lock`, into a temporary directory that is removed afterwards.
# Nothing outside that directory is written.
#
# A BROWSER BOOT IS THE AUTHORITATIVE ONE. Headless, the runtime measures
# text with a stand-in and never binds a backend, so every text has no
# height, every container that sizes to its content has no height either, and
# the layout checks that rest on geometry report overlaps that a browser does
# not have. With `DECLARE_VERIFY_REQUIRE_BROWSER=1` this script refuses to
# pass on a headless boot, so a CI run cannot report a layout verdict it did
# not actually measure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/declare-apps/xennic-platform"
APP="$APP_DIR/xennic-platform.declare"
LOCK="$APP_DIR/toolchain.lock"
DIST="$APP_DIR/dist"

if [ ! -f "$APP" ] || [ ! -f "$LOCK" ]; then
  echo "declare-verify: the Declare program or its toolchain lock is missing" >&2
  exit 2
fi

# The pin, read from the lock file: `key = value` lines, `#` for a comment.
pin() {
  sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" "$LOCK" | head -n 1
}
COMMIT="$(pin commit)"
REPO="$(pin repo)"
if [ -z "$COMMIT" ] || [ -z "$REPO" ]; then
  echo "declare-verify: $LOCK names no commit or no repository" >&2
  exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "declare-verify: toolchain $COMMIT"

# ── the toolchain ───────────────────────────────────────────────────────────
# A sparse checkout: the compiler, the runtime, the tools, the class library
# and the browser host are what the ladder and the rebuild run on. The
# examples, the reports and the bundles in the toolchain's own repository are
# not, and they are most of its size.
TOOLCHAIN="$WORK/declarelang"
mkdir -p "$TOOLCHAIN"
git -C "$TOOLCHAIN" init -q
git -C "$TOOLCHAIN" remote add origin "$REPO"
git -C "$TOOLCHAIN" config core.sparseCheckout true
# shellcheck disable=SC2016
printf 'compiler/\nruntime/\ntools/\nlibrary/\nbrowser/\npackage.json\npackage-lock.json\ntsconfig.json\n' \
  > "$TOOLCHAIN/.git/info/sparse-checkout"
git -C "$TOOLCHAIN" fetch -q --depth 1 --filter=blob:none origin "$COMMIT"
git -C "$TOOLCHAIN" checkout -q FETCH_HEAD

echo "declare-verify: installing the toolchain's own dependencies"
if ! (cd "$TOOLCHAIN" && npm ci --no-audit --no-fund >/dev/null); then
  echo "declare-verify: the toolchain's dependencies could not be installed." >&2
  echo "  The toolchain is fetched at the pinned commit; a failure here is" >&2
  echo "  usually the network, not the program." >&2
  exit 1
fi
# The toolchain ships its compiler and runtime compiled, but it rebuilds
# them here so the ladder runs against what this commit's sources make.
if ! (cd "$TOOLCHAIN" && npm run build >/dev/null); then
  echo "declare-verify: the toolchain did not build at $COMMIT." >&2
  exit 1
fi

# ── 1. the ladder ───────────────────────────────────────────────────────────
LOG="$WORK/verify.log"
# The log is kept where the caller asked for it, so a failing run's
# artefact says which rung failed and what it said. It is kept whether the
# ladder passed or not: a failure is exactly when it is wanted.
KEPT_LOG="${DECLARE_VERIFY_LOG:-}"
keep_log() {
  [ -n "$KEPT_LOG" ] || return 0
  mkdir -p "$(dirname "$KEPT_LOG")"
  cp "$LOG" "$KEPT_LOG" 2>/dev/null || true
}
if ! (cd "$TOOLCHAIN" && node tools/verify.mjs "$APP") 2>&1 | tee "$LOG"; then
  keep_log
  echo "declare-verify: the ladder did not pass" >&2
  exit 1
fi
keep_log

# A headless boot measures text with a stand-in and binds no backend, so the
# layout it reports is not the layout a reader gets. When the caller asks for
# an authoritative verdict, a headless boot is not one.
if [ "${DECLARE_VERIFY_REQUIRE_BROWSER:-0}" = "1" ] && ! grep -q 'in Chrome, real text' "$LOG"; then
  echo "declare-verify: no browser was found, so the boot was headless and its" >&2
  echo "  layout verdict is not the one a reader gets. Install Chrome (or set" >&2
  echo "  PUPPETEER_EXECUTABLE_PATH) and run this again." >&2
  exit 1
fi

# ── 2. the bundle ───────────────────────────────────────────────────────────
# Rebuilt into a scratch directory: the committed `dist/` is never written to
# by this script, so a failing check leaves the repository exactly as it was.
BUILT="$WORK/built"
mkdir -p "$BUILT"
(cd "$TOOLCHAIN" && node tools/declarec.mjs "$APP" -o "$BUILT" --kernel=js >/dev/null)

ENTRY="$(node -e 'const m=require(process.argv[1]);process.stdout.write(m.entry??"")' "$DIST/manifest.json")"
if [ -z "$ENTRY" ]; then
  echo "declare-verify: $DIST/manifest.json names no bundle" >&2
  exit 1
fi
if [ ! -f "$DIST/$ENTRY" ]; then
  echo "declare-verify: the manifest names $ENTRY, which is not in $DIST" >&2
  exit 1
fi

BUILT_ENTRY="$(node -e '
const { readdirSync } = require("node:fs")
const names = readdirSync(process.argv[1]).filter((n) => /^app\.[0-9a-f]+\.js$/.test(n))
if (names.length !== 1) { console.error(`expected one app.<hash>.js, found ${names.length}`); process.exit(1) }
process.stdout.write(names[0])
' "$BUILT")"

if [ "$ENTRY" != "$BUILT_ENTRY" ]; then
  echo "declare-verify: the committed bundle is $ENTRY, but a rebuild with the" >&2
  echo "  pinned toolchain makes $BUILT_ENTRY. The page asks for the committed" >&2
  echo "  name, so the rebuilt program would never be served." >&2
  exit 1
fi

if ! cmp -s "$DIST/$ENTRY" "$BUILT/$BUILT_ENTRY"; then
  echo "declare-verify: $ENTRY differs from a rebuild with the pinned toolchain." >&2
  echo "  The committed bundle is stale (or was changed by hand). Rebuild it" >&2
  echo "  and commit the result together with the toolchain pin." >&2
  exit 1
fi

echo "declare-verify: $ENTRY matches a rebuild with the pinned toolchain (sha256 $(sha256sum "$DIST/$ENTRY" | cut -c1-12)…)"
echo "declare-verify: the ladder passed and the published bundle is the one the pin builds."
