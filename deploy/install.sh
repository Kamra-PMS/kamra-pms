#!/usr/bin/env bash
# Kamra — self-host install (build the image on this machine, then compose up).
#
#   curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
#
# Or: clone the repo, cd deploy, ./install.sh
#
# Builds Frappe + payments + kamra locally via frappe_docker's layered
# Containerfile. Does NOT pull from ghcr.io (kept private for Kamra's own
# demo/nightly hosts). First install often takes 20–45 minutes.
#
# Asks three things (or reads env): SITE_NAME, ADMIN_EMAIL, ADMIN_PASSWORD.
# Creates the Frappe site, installs payments + kamra, enables the scheduler,
# points / at /kamra. There is no default password.
#
# Modes:
#   install.sh            install (safe to re-run; reuses DB password + site)
#   install.sh update     rebuild the image from apps.json, restart, migrate
#   install.sh build      build the image only (Packer / 1-Click snapshots)
#
# The installer copies itself to $INSTALL_DIR/install.sh, so updates are:
#   sudo /opt/kamra/install.sh update
set -euo pipefail

MODE="${1:-install}"
case "$MODE" in
  install|update|build) ;;
  *) echo "usage: install.sh [install|update|build]" >&2; exit 2 ;;
esac

KAMRA_IMAGE="${KAMRA_IMAGE:-kamra}"
KAMRA_TAG="${KAMRA_TAG:-local}"
KAMRA_GIT_URL="${KAMRA_GIT_URL:-https://github.com/Kamra-PMS/kamra-pms}"
KAMRA_BRANCH_OVERRIDE="${KAMRA_BRANCH:-}"
KAMRA_BRANCH="${KAMRA_BRANCH:-main}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
FRAPPE_PATH="${FRAPPE_PATH:-https://github.com/frappe/frappe}"
INSTALL_DIR="${INSTALL_DIR:-/opt/kamra}"
FRAPPE_DOCKER_REPO="${FRAPPE_DOCKER_REPO:-https://github.com/frappe/frappe_docker.git}"
# Pinned so an upstream change can't break every fresh install. Bump
# deliberately after the deploy-smoke CI job passes on the new ref.
FRAPPE_DOCKER_REF="${FRAPPE_DOCKER_REF:-3d0a0e53d8ab03903f6c3f125976a37d7a0f9875}"
FORCE_REBUILD="${FORCE_REBUILD:-0}"
MIN_PASSWORD_LEN=10
# Build RAM floor (MiB, RAM + swap). Below this we add a swap file.
BUILD_MEM_MB=8000
ENVFILE="$INSTALL_DIR/kamra.env"
APPS_JSON="$INSTALL_DIR/apps.json"

red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
die() { red "error: $*"; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "need '$1' on PATH"; }

# When piped (curl | bash), stdin is the script — reopen the terminal for prompts.
if [ "$MODE" = install ] && [ ! -t 0 ] && [ -z "${SITE_NAME:-}" ]; then
  exec < /dev/tty || die "cannot read prompts (run: bash install.sh, or export SITE_NAME ADMIN_EMAIL ADMIN_PASSWORD)"
fi

prompt() {
  local var="$1" label="$2" secret="${3:-}"
  if [ -n "${!var:-}" ]; then
    return 0
  fi
  if [ -n "$secret" ]; then
    read -r -s -p "$label: " value
    echo
  else
    read -r -p "$label: " value
  fi
  export "$var=$value"
}

echo
echo "  Kamra — open-source hotel PMS"
echo "  https://kamrapms.com"
echo
echo "  This installer builds the Docker image on THIS server"
echo "  (Frappe + payments + kamra). Plan for 20–45 minutes and"
echo "  40 GB disk. Under 8 GB RAM a swap file is added for the build."
echo

# --- Docker -----------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Installing Docker Engine…"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker 2>/dev/null || true
fi
need_cmd docker
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 required (docker compose)"
# layered Containerfile uses RUN --mount=type=secret, which needs BuildKit
# via buildx. Ubuntu's docker.io package ships without it.
if ! docker buildx version >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing docker buildx…"
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker-buildx >/dev/null 2>&1 \
      || DEBIAN_FRONTEND=noninteractive apt-get install -y docker-buildx-plugin >/dev/null 2>&1 || true
  fi
  docker buildx version >/dev/null 2>&1 || die "docker buildx is required (apt install docker-buildx-plugin)"
fi
export DOCKER_BUILDKIT=1

# --- helpers used by every mode ---------------------------------------------
ensure_build_memory() {
  local mem_mb swap_mb need_mb
  mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
  swap_mb=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
  [ "$mem_mb" -gt 0 ] || return 0  # not Linux; let docker decide
  if [ $((mem_mb + swap_mb)) -ge "$BUILD_MEM_MB" ]; then
    return 0
  fi
  need_mb=$((BUILD_MEM_MB - mem_mb - swap_mb))
  [ "$need_mb" -lt 2048 ] && need_mb=2048
  if [ -e /swapfile-kamra ]; then
    swapon /swapfile-kamra 2>/dev/null || true
    return 0
  fi
  echo "Only ${mem_mb} MB RAM + ${swap_mb} MB swap — adding a ${need_mb} MB swap file for the build…"
  if fallocate -l "${need_mb}M" /swapfile-kamra 2>/dev/null \
    || dd if=/dev/zero of=/swapfile-kamra bs=1M count="$need_mb" status=none; then
    chmod 600 /swapfile-kamra
    mkswap /swapfile-kamra >/dev/null
    swapon /swapfile-kamra
    grep -q '^/swapfile-kamra ' /etc/fstab 2>/dev/null \
      || echo '/swapfile-kamra none swap sw 0 0' >> /etc/fstab
  else
    red "warning: could not add swap; the build may run out of memory"
  fi
}

checkout_frappe_docker() {
  mkdir -p "$INSTALL_DIR"
  if [ ! -d "$INSTALL_DIR/frappe_docker/.git" ]; then
    echo "Fetching frappe_docker@${FRAPPE_DOCKER_REF:0:12} → $INSTALL_DIR/frappe_docker"
    git init -q "$INSTALL_DIR/frappe_docker"
    git -C "$INSTALL_DIR/frappe_docker" remote add origin "$FRAPPE_DOCKER_REPO"
  fi
  if [ "$(git -C "$INSTALL_DIR/frappe_docker" rev-parse HEAD 2>/dev/null)" != "$FRAPPE_DOCKER_REF" ]; then
    git -C "$INSTALL_DIR/frappe_docker" fetch -q --depth 1 origin "$FRAPPE_DOCKER_REF"
    git -C "$INSTALL_DIR/frappe_docker" checkout -q --force FETCH_HEAD
  fi
  cd "$INSTALL_DIR/frappe_docker"
}

write_apps_json() {
  cat > "$APPS_JSON" <<EOF
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "${KAMRA_GIT_URL}", "branch": "${KAMRA_BRANCH}"}
]
EOF
}

# CACHE_BUST changes every run, so Docker re-runs `bench init` and fetches
# the current apps. (The apps.json secret alone does not bust the cache.)
build_image() {
  ensure_build_memory
  echo "Building ${KAMRA_IMAGE}:${KAMRA_TAG} from ${KAMRA_GIT_URL}@${KAMRA_BRANCH}…"
  echo "  (first build downloads the Frappe toolchain — go stretch)"
  docker build \
    -t "${KAMRA_IMAGE}:${KAMRA_TAG}" \
    -f images/layered/Containerfile \
    --build-arg "FRAPPE_PATH=${FRAPPE_PATH}" \
    --build-arg "FRAPPE_BRANCH=${FRAPPE_BRANCH}" \
    --build-arg "CACHE_BUST=${KAMRA_BRANCH}-$(date +%s)" \
    --secret "id=apps_json,src=${APPS_JSON}" \
    . || die "docker build failed — see output above (disk full? out of memory?)"
}

compose() {
  docker compose --project-name kamra --env-file "$ENVFILE" \
    -f compose.yaml \
    -f overrides/compose.mariadb.yaml \
    -f overrides/compose.redis.yaml \
    -f overrides/compose.noproxy.yaml "$@"
}

wait_for_backend() {
  echo "Waiting for MariaDB and backend…"
  for _ in $(seq 1 60); do
    if compose exec -T backend bench --version >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  die "backend did not become ready — check: docker compose -p kamra logs"
}

install_self() {
  # Keep a copy next to the stack so `install.sh update` works later.
  local self="${BASH_SOURCE[0]:-}"
  if [ -n "$self" ] && [ -f "$self" ] && [ "$self" != "$INSTALL_DIR/install.sh" ]; then
    cp "$self" "$INSTALL_DIR/install.sh" && chmod +x "$INSTALL_DIR/install.sh"
  elif [ ! -f "$INSTALL_DIR/install.sh" ]; then
    curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh \
      -o "$INSTALL_DIR/install.sh" && chmod +x "$INSTALL_DIR/install.sh" || true
  fi
}

# --- build: image only (Packer / Marketplace snapshots) ---------------------
if [ "$MODE" = build ]; then
  checkout_frappe_docker
  write_apps_json
  build_image
  install_self
  green "Built ${KAMRA_IMAGE}:${KAMRA_TAG}. First boot: ${INSTALL_DIR}/install.sh"
  exit 0
fi

# --- update: rebuild from the recorded apps.json, restart, migrate ----------
if [ "$MODE" = update ]; then
  [ -f "$ENVFILE" ] || die "no ${ENVFILE} — run install first"
  [ -f "$APPS_JSON" ] || die "no ${APPS_JSON} — run install first"
  checkout_frappe_docker
  # KAMRA_BRANCH=… on the command line switches branch/tag; otherwise keep
  # whatever apps.json already records.
  if [ -n "${KAMRA_BRANCH_OVERRIDE:-}" ]; then
    KAMRA_BRANCH="$KAMRA_BRANCH_OVERRIDE"
    write_apps_json
  else
    KAMRA_BRANCH=$(grep -o '"branch": *"[^"]*"' "$APPS_JSON" | tail -1 | sed 's/.*"\([^"]*\)"$/\1/')
  fi
  build_image
  echo "Restarting the stack on the new image…"
  compose up -d --force-recreate
  wait_for_backend
  echo "Migrating sites…"
  compose exec -T backend bench --site all migrate
  compose exec -T backend bench --site all clear-cache
  install_self
  green "Kamra updated to ${KAMRA_GIT_URL}@${KAMRA_BRANCH}."
  exit 0
fi

# --- Prompts (WordPress install.php shape) ----------------------------------
# Non-interactive (cloud-init / 1-click): export SITE_NAME ADMIN_EMAIL ADMIN_PASSWORD first.
if [ -z "${SITE_NAME:-}" ] || [ -z "${ADMIN_EMAIL:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  prompt SITE_NAME "Site domain (e.g. pms.yourhotel.com)"
  prompt ADMIN_EMAIL "Admin email"
  prompt ADMIN_PASSWORD "Admin password (min ${MIN_PASSWORD_LEN} chars)" secret
  prompt ADMIN_PASSWORD_CONFIRM "Confirm admin password" secret
  [ "${ADMIN_PASSWORD}" = "${ADMIN_PASSWORD_CONFIRM}" ] || die "passwords do not match"
fi

[ -n "${SITE_NAME}" ] || die "SITE_NAME is required"
[[ "${SITE_NAME}" == *.* ]] || die "SITE_NAME should look like a domain (pms.yourhotel.com)"
[[ "${ADMIN_EMAIL}" == *@* ]] || die "ADMIN_EMAIL must be an email address"
[ "${#ADMIN_PASSWORD}" -ge "$MIN_PASSWORD_LEN" ] || die "password must be at least ${MIN_PASSWORD_LEN} characters"

# Re-runs must keep the DB password MariaDB was initialised with.
if [ -z "${DB_PASSWORD:-}" ] && [ -f "$ENVFILE" ]; then
  DB_PASSWORD=$(sed -n 's/^DB_PASSWORD=//p' "$ENVFILE" | head -1)
fi
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 32)}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$ADMIN_EMAIL}"
HTTP_PUBLISH_PORT="${HTTP_PUBLISH_PORT:-8080}"

# --- frappe_docker checkout + image -----------------------------------------
checkout_frappe_docker
write_apps_json

# 1-Click snapshots ship a pre-built image; plain re-runs reuse it too.
if docker image inspect "${KAMRA_IMAGE}:${KAMRA_TAG}" >/dev/null 2>&1 && [ "$FORCE_REBUILD" != "1" ]; then
  echo "Image ${KAMRA_IMAGE}:${KAMRA_TAG} already present — skipping build."
  echo "  (to pull new Kamra code later: ${INSTALL_DIR}/install.sh update)"
else
  build_image
fi

umask 077
cat > "$ENVFILE" <<EOF
# Generated by Kamra install.sh — do not commit.
DB_PASSWORD=${DB_PASSWORD}
CUSTOM_IMAGE=${KAMRA_IMAGE}
CUSTOM_TAG=${KAMRA_TAG}
# never: image is local; do not hit a registry
PULL_POLICY=never
# compose still interpolates this even with CUSTOM_IMAGE set
ERPNEXT_VERSION=${KAMRA_TAG}
FRAPPE_SITE_NAME_HEADER=${SITE_NAME}
HTTP_PUBLISH_PORT=${HTTP_PUBLISH_PORT}
EOF

umask 022

echo "Starting the stack with local image ${KAMRA_IMAGE}:${KAMRA_TAG}…"
compose up -d
wait_for_backend

# Idempotent: skip new-site only if this site already has a site_config.json
# (sites/ also holds apps.txt, apps.json, assets, common_site_config.json).
if ! compose exec -T backend test -f "sites/${SITE_NAME}/site_config.json"; then
  echo "Creating site ${SITE_NAME} (this takes a few minutes)…"
  compose exec -T backend bench new-site "$SITE_NAME" \
    --mariadb-user-host-login-scope='%' \
    --db-root-password "$DB_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --install-app payments --install-app kamra --no-mariadb-socket
else
  echo "Site ${SITE_NAME} already present — skipping new-site."
fi

echo "First-boot wiring (home → /kamra, admin email, scheduler)…"
compose exec -T \
  -e "KAMRA_ADMIN_EMAIL=${ADMIN_EMAIL}" \
  -e "KAMRA_SITE_URL=https://${SITE_NAME}" \
  backend bench --site "$SITE_NAME" execute kamra.scripts.first_boot.execute

# Never leave the password sitting in the shell history file if we can help it
unset ADMIN_PASSWORD ADMIN_PASSWORD_CONFIRM
# Strip any leftover from a previous interactive shell export
export ADMIN_PASSWORD=""

green ""
green "Kamra is up."
green "  Sign in:  http://<server-ip>:${HTTP_PUBLISH_PORT}/kamra"
green "            (or https://${SITE_NAME} after you point DNS + TLS)"
green "  User:     Administrator  (email ${ADMIN_EMAIL})"
green "  Password: the one you just set — there is no default."
green "  Next:     open /kamra/setup and create your property."
green ""
green "TLS tip: put nginx/Caddy in front, or:"
green "  certbot --nginx -d ${SITE_NAME}"
green ""
install_self
green "Stack dir: ${INSTALL_DIR}   env: ${ENVFILE}   apps: ${APPS_JSON}"
green "Update later (rebuilds the image, restarts, migrates):"
green "  sudo ${INSTALL_DIR}/install.sh update"
