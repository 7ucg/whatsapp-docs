#!/usr/bin/env bash
# Build the static site into ./site (extra css/js get a content hash for cache busting)
set -euo pipefail
cd "$(dirname "$0")"
rm -rf .site-src site && mkdir .site-src
cp -r site-extra/. .site-src/
cp WA_*.md CHANGELOG.md .site-src/
sed -i "/^\*\*Version:\*\*/s/\$/  /" .site-src/WA_*.md
h=$(cat site-extra/javascripts/extra.js site-extra/stylesheets/extra.css | sha1sum | cut -c1-8)
sed -E "s#(stylesheets/extra\.css|javascripts/extra\.js)#\1?v=$h#" mkdocs.yml > .mkdocs.build.yml
.venv/bin/mkdocs build -q -f .mkdocs.build.yml 2>&1 | grep -vE '^\S*\s*[│╷╵]|MkDocs 2|squidfunk|^\s*$' || true
rm -f .mkdocs.build.yml
echo "built: $(pwd)/site (v=$h)"
