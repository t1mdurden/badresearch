#!/usr/bin/env bash
# Vendor the `oc` CLI (github.com/only-cli/oc) into vendor/oc for the rung-1.5 provider.
#
# Not run automatically and its output is NOT committed. `oc` declares MIT in its README
# badge and package.json but ships no LICENSE file, so GitHub reports `license: null`
# and the grant is a claim rather than a licence. This repository is public; committing
# someone else's unlicensed source into it is a different decision from running their
# published package locally. Track github.com/only-cli/oc/issues/15 — once a LICENSE
# lands, drop vendor/ from .gitignore and commit the checkout.
#
# Until then this script gives the same result on any machine: a pinned checkout that
# `browse/oc.py::_resolve_cli` finds ahead of anything on PATH.
set -euo pipefail

REF="${1:-v0.3.0-beta.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/vendor/oc"

command -v node >/dev/null || { echo "vendor-oc: node is required (>=20)" >&2; exit 1; }
command -v npm  >/dev/null || { echo "vendor-oc: npm is required" >&2; exit 1; }

rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
git clone --quiet --depth 1 --branch "$REF" https://github.com/only-cli/oc.git "$DEST"

# --omit=optional skips `impers`, the native libcurl-impersonate binding. Without it the
# CLI falls back to plain fetch with Chrome's headers, which is what the rung-1.5 measure
# was taken on. Pass VENDOR_OC_WITH_IMPERS=1 to install it and get the TLS fingerprint too.
if [ "${VENDOR_OC_WITH_IMPERS:-0}" = "1" ]; then
  ( cd "$DEST" && npm install --no-audit --no-fund >/dev/null )
else
  ( cd "$DEST" && npm install --omit=optional --no-audit --no-fund >/dev/null )
fi

rm -rf "$DEST/.git"
node "$DEST/src/cli.js" --help >/dev/null
echo "vendor-oc: $REF installed at $DEST"
