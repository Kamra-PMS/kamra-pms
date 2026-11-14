#!/usr/bin/env bash
# Bench-path update with the same hard rule as install.sh update:
#   no backup → no update.
# Usage: ./deploy/update-bench.sh <site> [kamra-git-ref]
#   site   e.g. jaref.kamrapms.com
#   ref    optional branch/tag for apps/kamra (default: current branch pull)
set -euo pipefail

SITE="${1:-}"
REF="${2:-}"
[ -n "$SITE" ] || { echo "usage: $0 <site> [git-ref]" >&2; exit 2; }

die() { echo "error: $*" >&2; exit 1; }

command -v bench >/dev/null || die "bench not on PATH (run from the frappe-bench root)"
[ -d apps/kamra ] || die "run from the frappe-bench root (apps/kamra missing)"

echo "Backing up ${SITE} (bench backup --with-files)…"
bench --site "$SITE" backup --with-files \
  || die "backup failed — update aborted, site untouched"
echo "  backups: sites/${SITE}/private/backups"

echo "Updating kamra…"
if [ -n "$REF" ]; then
  git -C apps/kamra fetch --tags origin
  git -C apps/kamra checkout "$REF"
  git -C apps/kamra pull --ff-only origin "$REF" 2>/dev/null \
    || git -C apps/kamra pull --ff-only
else
  git -C apps/kamra pull --ff-only
fi

echo "Migrating ${SITE}…"
bench --site "$SITE" migrate
bench build --app kamra
bench --site "$SITE" clear-cache
bench restart

echo "Done. Kamra on ${SITE} updated after a successful backup."
