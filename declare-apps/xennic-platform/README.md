# Xennic Platform — Declare source

The three engineering calculators on `/platform`, written in
[Declare](https://github.com/davidtemkin/declarelang). This folder is the
source; `public/declare-platform/` is the build the browser downloads.

```
xennic-platform.declare   the app: formulas, inputs, three panels
parts.declare             palette as a theme, and the small views both use
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
  -o ../../public/declare-platform --kernel=js
node tools/manifest.mjs                                            # see below
```

`--kernel=js` is deliberate: the site's pages are cached at the edge and may be
served under a policy that forbids WebAssembly, and a precompiled bundle needs
no in-browser compiler at all.

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
for that exact name, so the build also writes
`public/declare-platform/manifest.json` with the file it just produced. Nothing
else reads it, and a stale manifest cannot happen while the two are built and
committed together — the smoke test fetches the entry and fails if it 404s.
