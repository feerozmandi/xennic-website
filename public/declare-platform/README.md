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

## The manifest

`declarec` names its bundle after a hash of the content. The island has to ask
for that exact name, so the build also writes
`public/declare-platform/manifest.json` with the file it just produced. Nothing
else reads it, and a stale manifest cannot happen while the two are built and
committed together — the smoke test fetches the entry and fails if it 404s.
