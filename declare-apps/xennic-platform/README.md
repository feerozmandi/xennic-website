# Xennic Platform — Declare source

The three engineering calculators on `/platform`, written in
[Declare](https://github.com/davidtemkin/declarelang). This folder is the
source; `dist/` is the build the website publishes.

```
xennic-platform.declare   the app: formulas, inputs, three panels
parts.declare             palette as a theme, and the small views both use
tools/manifest.mjs        writes the manifest after a build
dist/                     the compiled program, its build record and the manifest
```

## Building

The toolchain is a dependency of this folder, not of the website (the site's
`npm ci` must not fetch a compiler it never runs):

```bash
git clone https://github.com/davidtemkin/declarelang /tmp/declarelang
cd /tmp/declarelang && npm ci

cd declare-apps/xennic-platform
node /tmp/declarelang/tools/verify.mjs xennic-platform.declare      # R1–R4 must be clean
node /tmp/declarelang/tools/declarec.mjs xennic-platform.declare \
  -o dist --kernel=js
node tools/manifest.mjs                                            # see below
```

`declarec` empties the output folder, so `dist/` holds exactly what the
compiler wrote. It also copies this folder's `README.md` and `tools/` next to
the program; those copies are ignored by git, because the originals live
here.

`--kernel=js` is deliberate: the site's pages are cached at the edge and may be
served under a policy that forbids WebAssembly, and a precompiled bundle needs
no in-browser compiler at all.

## How the program reaches the browser

`scripts/declare-platform.mjs` in the website does it, in three steps:

- **prepare** (before `next build`) writes the bundle's name into
  `src/lib/declare-platform.generated.ts`. The name is a hash of the
  program's content, so it cannot be typed by hand — a stale name would be a
  404 on a page that otherwise looks fine.
- **publish** (after `next build`) copies the program into
  `.next/static/declare-platform/`, where it is served as
  `/_next/static/declare-platform/app.<hash>.js`.
- **dev** copies the same file into `public/` and tells the development
  server to use that path, because the development server has no build output.

The publication path is not a detail. The public edge lists its public paths
explicitly, and a path that is not on that list is answered with a sign-in
redirect instead of the file. `/_next/static/*` is on that list, because it
is where the site's own build artifacts live; a compiled program belongs with
them. Changing the edge's list is an operation on the live edge with its own
reviewed hashes — a build artifact does not deserve that.

## Two things the language does not do for us

**Layouts are not mirrored.** A row lays out from the left, whatever the
direction, so in a right-to-left page the *first* child of a row has to be
written *last*: the tab bar, the province picker, every row of figures, the
number field beside its slider and the triage checkboxes are all declared in
the reverse of the reading order. The program's `direction = rtl` makes the
text right-to-left; it does not move the boxes.

**A `datapath` may only point at declared data.** The priority list is
computed, so it lands in a derived dataset (`priorityList`) and the rows read
that — a view cannot bind to a computed array.

The slider is the one exception that was left alone: the library defines
`min` as the value at the left end, and mirroring the control would invert
what a drag means. The number beside it always shows the value.

## The manifest

`declarec` names its bundle after a hash of the content. The island has to ask
for that exact name, so the build also writes `dist/manifest.json` with the
file it just produced. Nothing else reads it, and a stale manifest cannot
happen while the two are built and committed together — the smoke test reads
the manifest from disk, fetches the program by that name and fails if the
bytes are not the ones the build produced.
