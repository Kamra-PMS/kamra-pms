#!/usr/bin/env bash
# Ensure ghcr.io/kamra-pms/kamra is anonymously pullable (install.sh / one-click).
# GHCR packages default to private; self-host pulls need Public.
# Idempotent. First-time org publishes may still need a one-click admin confirm
# in the GitHub UI if the org has not allowed public packages yet.
set -euo pipefail

ORG="${GHCR_ORG:-Kamra-PMS}"
PACKAGE="${GHCR_PACKAGE:-kamra}"

if [ -z "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ]; then
  echo "make-ghcr-public: no GH_TOKEN/GITHUB_TOKEN — skipping"
  exit 0
fi
export GH_TOKEN="${GH_TOKEN:-$GITHUB_TOKEN}"

echo "Setting package ${ORG}/${PACKAGE} (container) visibility → public…"
if gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/orgs/${ORG}/packages/container/${PACKAGE}/visibility" \
  -f visibility=public; then
  echo "Package is public."
  exit 0
fi

echo "::warning::Could not set GHCR package visibility to public."
echo "An org admin must open:"
echo "  https://github.com/orgs/${ORG}/packages/container/package/${PACKAGE}"
echo "→ Package settings → Change visibility → Public"
# Do not fail the publish job — image push already succeeded.
exit 0
