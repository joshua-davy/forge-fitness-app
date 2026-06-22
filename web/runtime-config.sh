#!/bin/sh
set -eu

# Render provides service environment variables at container runtime. Keep the
# value outside the build artefact so staging/production can use different APIs.
api_url="${FORGE_API_URL:-}"
case "$api_url" in
  ""|https://*|http://localhost:*|http://127.0.0.1:*) ;;
  *) echo "FORGE_API_URL must be an http(s) URL" >&2; exit 1 ;;
esac
printf 'window.__FORGE_API_URL__ = "%s";\n' "$api_url" > /usr/share/nginx/html/runtime-config.js
