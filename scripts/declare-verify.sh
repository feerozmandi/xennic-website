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
# The toolchain is fetched, installed and built on every run, which is the
# slowest part of this check and the part that fails when the network
# misbehaves. A caller that keeps a directory of its own can have the
# built toolchain kept there and reused, which is what CI does.
CACHE_DIR="${DECLARE_VERIFY_CACHE:-}"
trap '[ -z "$CACHE_DIR" ] && rm -rf "$WORK" || rm -rf "$WORK"' EXIT

echo "declare-verify: toolchain $COMMIT"

# ── the toolchain ───────────────────────────────────────────────────────────
# A sparse checkout: the compiler, the runtime, the tools, the class library
# and the browser host are what the ladder and the rebuild run on. The
# examples, the reports and the bundles in the toolchain's own repository are
# not, and they are most of its size.
TOOLCHAIN="$WORK/declarelang"
CACHED_TOOLCHAIN="$CACHE_DIR/toolchain"
# A cached toolchain is the same commit, so it is the same compiler. It is
# used when it is there, and fetched and built when it is not.
use_cached=0
if [ -n "$CACHE_DIR" ] && [ -d "$CACHED_TOOLCHAIN/.git" ] && [ -d "$CACHED_TOOLCHAIN/node_modules" ]; then
  cp -a "$CACHED_TOOLCHAIN" "$TOOLCHAIN"
  use_cached=1
  echo "declare-verify: using the toolchain kept from an earlier run"
fi
if [ "$use_cached" = "0" ]; then
  mkdir -p "$TOOLCHAIN"
  git -C "$TOOLCHAIN" init -q
  git -C "$TOOLCHAIN" remote add origin "$REPO"
  git -C "$TOOLCHAIN" config core.sparseCheckout true
  # shellcheck disable=SC2016
  printf 'compiler/\nruntime/\ntools/\nlibrary/\nbrowser/\npackage.json\npackage-lock.json\ntsconfig.json\n' \
    > "$TOOLCHAIN/.git/info/sparse-checkout"
  # The toolchain is fetched over the network, and a network that drops a
  # connection now and then is not a verdict on the program. So it is fetched
  # again, a few times, before the run gives up.
  fetched=0
  for attempt in 1 2 3 4 5; do
    if git -C "$TOOLCHAIN" fetch -q --depth 1 --filter=blob:none origin "$COMMIT" 2>/dev/null; then
      fetched=1
      break
    fi
    echo "declare-verify: fetching the toolchain failed (attempt $attempt), trying again" >&2
    sleep $((attempt * 5))
  done
  if [ "$fetched" != "1" ]; then
    echo "declare-verify: the toolchain at $COMMIT could not be fetched from $REPO." >&2
    echo "  This is the network, not the program." >&2
    exit 1
  fi
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
  # A built toolchain is worth keeping: it is the same commit, so it is the
  # same compiler, and the next run does not have to fetch, install and build
  # it again.
  if [ -n "$CACHE_DIR" ]; then
    mkdir -p "$CACHE_DIR"
    rm -rf "$CACHE_DIR/toolchain"
    cp -a "$TOOLCHAIN" "$CACHE_DIR/toolchain"
    echo "declare-verify: the built toolchain was kept at $CACHE_DIR/toolchain"
  fi
  fi

  # ── the browser ─────────────────────────────────────────────────────────────
  # The toolchain launches the browser itself, and the flags it passes are
  # the ones a developer's own machine needs. On a CI runner the browser
  # runs in a container: it needs to be told not to use the sandbox (which
  # the runner's user may not) and not to use /dev/shm (which the runner
  # keeps small), or it dies mid-run and takes the process driving it with
  # it.
  #
  # So the browser is put behind a wrapper that adds those flags, and the
  # toolchain is pointed at the wrapper. Nothing else changes: every other
  # flag the toolchain passes is handed over untouched.
  CHROME_WRAPPER="$WORK/chrome-with-ci-flags.sh"
  cp "$ROOT/scripts/chrome-with-ci-flags.sh" "$CHROME_WRAPPER"
  chmod +x "$CHROME_WRAPPER"
  REAL_CHROME="${CHROME_PATH:-${PUPPETEER_EXECUTABLE_PATH:-}}"
  if [ -z "$REAL_CHROME" ] || [ ! -x "$REAL_CHROME" ]; then
    # No browser was named: the toolchain looks in the usual places and
    # finds the runner's own Chrome, which needs the same flags.
    for candidate in /usr/bin/google-chrome /usr/bin/google-chrome-stable /usr/bin/chromium /usr/bin/chromium-browser; do
      if [ -x "$candidate" ]; then
        REAL_CHROME="$candidate"
        break
      fi
    done
  fi
  if [ -n "$REAL_CHROME" ] && [ -x "$REAL_CHROME" ]; then
    export DECLARE_REAL_CHROME="$REAL_CHROME"
    export CHROME_PATH="$CHROME_WRAPPER"
    # What the browser itself says is kept: the toolchain starts the browser
    # with its output thrown away, so a browser that refuses to start says
    # nothing at all, and the run reports only that the browser did not
    # start. With the words kept, the reason is in the run.
    export DECLARE_CHROME_LOG="$WORK/chrome.log"
    echo "declare-verify: the browser is $REAL_CHROME, behind a wrapper that adds the flags a runner needs"

    # THE WRAPPER IS CHECKED BEFORE IT IS BELIEVED. A wrapper that bash
    # cannot parse never runs: the browser is never started, and the
    # toolchain says only that a kept Chrome did not start, which names the
    # symptom and not the cause. That is what happened here once, and it
    # cost a run to find out. So the wrapper is asked to start the browser
    # before the ladder runs, and a wrapper that cannot is named as such.
    if ! bash -n "$CHROME_WRAPPER" 2>"$WORK/wrapper-syntax.log"; then
      echo "declare-verify: the wrapper is not valid bash, so the browser would" >&2
      echo "  never start. What bash says:" >&2
      sed 's/^/  /' "$WORK/wrapper-syntax.log" >&2
      exit 1
    fi
    if ! "$CHROME_WRAPPER" --version >/dev/null 2>"$WORK/wrapper-run.log"; then
      echo "declare-verify: the wrapper could not start the browser at $REAL_CHROME." >&2
      echo "  What it says:" >&2
      sed 's/^/  /' "$WORK/wrapper-run.log" >&2
      exit 1
    fi
    echo "declare-verify: the wrapper starts the browser and says: $("$CHROME_WRAPPER" --version 2>/dev/null || echo unknown)"
  else
    echo "declare-verify: no browser was found; the ladder will boot in Node." >&2
  fi

  # ── the machine ─────────────────────────────────────────────────────────────
  # A run that is killed leaves a log that stops in the middle of a line.
  # Which machine it was killed on is the difference between a bug in the
  # program and a runner that ran out of something, so what the machine had
  # is written down next to the program's own words.
  DIAG="$WORK/machine.txt"
  {
    echo "date            : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "runner          : ${GITHUB_RUNNER_NAME:-${GITHUB_RUNNER_OS:-unknown}}"
    echo "node            : $(node --version 2>/dev/null || echo unknown)"
    echo "browser         : ${REAL_CHROME:-none}"
    echo "browser wrapper : ${CHROME_PATH:-none}"
    if [ -n "$REAL_CHROME" ] && [ -x "$REAL_CHROME" ]; then
      echo "browser version : $("$REAL_CHROME" --version 2>/dev/null || echo 'could not be asked')"
    fi
    echo "memory          : $(free -m 2>/dev/null | awk '/^Mem:/ {print $2 " MiB total, " $7 " MiB free"}' || echo unknown)"
    echo "shm             : $(df -h /dev/shm 2>/dev/null | awk 'NR==2 {print $2 " total, " $4 " free"}' || echo unknown)"
    echo "disk            : $(df -h "$WORK" 2>/dev/null | awk 'NR==2 {print $2 " total, " $4 " free"}' || echo unknown)"
    echo "cpus            : $(nproc 2>/dev/null || echo unknown)"
    echo "cgroup memory   : $(cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || echo unknown)"
    echo "toolchain       : $(du -sh "$TOOLCHAIN" 2>/dev/null | cut -f1 || echo unknown)"
    echo "kept toolchain  : $( [ -n "$CACHE_DIR" ] && du -sh "$CACHED_TOOLCHAIN" 2>/dev/null | cut -f1 || echo none)"
  } > "$DIAG" 2>&1 || true

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
    cp "$DIAG" "${KEPT_LOG%.log}-machine.txt" 2>/dev/null || true
    # The browser's own words travel with the run: a browser that refused
    # to start said why here, and that is the whole finding.
    [ -f "$WORK/chrome.log" ] && cp "$WORK/chrome.log" "${KEPT_LOG%.log}-chrome.log" 2>/dev/null || true
    return 0
  }
  ladder_status=0
  (cd "$TOOLCHAIN" && node tools/verify.mjs "$APP") 2>&1 | tee "$LOG" || ladder_status=$?
  # How the ladder ended is part of what the run was given, so it is written
  # with the machine's facts and not into the ladder's own words.
  {
    echo "ladder status   : $ladder_status"
    if [ "$ladder_status" -gt 128 ]; then
      echo "ladder killed by: signal $((ladder_status - 128))"
    fi
    echo "log ends with    : $( [ -s "$LOG" ] && tail -c 1 "$LOG" | od -c | head -n 1 | sed 's/^ *//' || echo empty)"
  } >> "$DIAG" 2>&1 || true
  keep_log
  if [ "$ladder_status" != "0" ]; then
    # A process that was killed leaves a log that stops in the middle of a
    # line. That is not a verdict on the program, and saying so is the
    # difference between a bug and a machine that ran out of room.
    if [ "$(tail -c 1 "$LOG" | wc -l)" = "0" ] && [ -s "$LOG" ]; then
      echo "declare-verify: the ladder stopped in the middle of a line, so it" >&2
      echo "  was killed rather than finished. That is the machine, not the" >&2
      echo "  program; the last line it reached is in the log." >&2
    else
      echo "declare-verify: the ladder did not pass" >&2
    fi
    exit 1
  fi

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
