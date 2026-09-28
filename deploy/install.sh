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
set -euo pipefail

KAMRA_IMAGE="${KAMRA_IMAGE:-kamra}"
KAMRA_TAG="${KAMRA_TAG:-local}"
KAMRA_GIT_URL="${KAMRA_GIT_URL:-https://github.com/Kamra-PMS/kamra-pms}"
KAMRA_BRANCH="${KAMRA_BRANCH:-main}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
FRAPPE_PATH="${FRAPPE_PATH:-https://github.com/frappe/frappe}"
INSTALL_DIR="${INSTALL_DIR:-/opt/kamra}"
FRAPPE_DOCKER_REPO="${FRAPPE_DOCKER_REPO:-https://github.com/frappe/frappe_docker.git}"
FORCE_REBUILD="${FORCE_REBUILD:-0}"
MIN_PASSWORD_LEN=10

red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
die() { red "error: $*"; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "need '$1' on PATH"; }

# When piped (curl | bash), stdin is the script — reopen the terminal for prompts.
if [ ! -t 0 ] && [ -z "${SITE_NAME:-}" ]; then
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
echo "  roughly 8 GB RAM / 40 GB disk during the build."
echo

# --- Docker -----------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Installing Docker Engine…"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker 2>/dev/null || true
fi
need_cmd docker
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 required (docker compose)"
# layered Containerfile uses RUN --mount=type=secret
export DOCKER_BUILDKIT=1

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

DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 32)}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$ADMIN_EMAIL}"
HTTP_PUBLISH_PORT="${HTTP_PUBLISH_PORT:-8080}"

# --- frappe_docker checkout -------------------------------------------------
mkdir -p "$(dirname "$INSTALL_DIR")"
if [ ! -d "$INSTALL_DIR/frappe_docker/.git" ]; then
  echo "Cloning frappe_docker → $INSTALL_DIR/frappe_docker"
  git clone --depth 1 "$FRAPPE_DOCKER_REPO" "$INSTALL_DIR/frappe_docker"
fi
cd "$INSTALL_DIR/frappe_docker"

APPS_JSON="$INSTALL_DIR/apps.json"
cat > "$APPS_JSON" <<EOF
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "${KAMRA_GIT_URL}", "branch": "${KAMRA_BRANCH}"}
]
EOF

# --- Build image locally (no ghcr.io pull) ----------------------------------
if docker image inspect "${KAMRA_IMAGE}:${KAMRA_TAG}" >/dev/null 2>&1 && [ "$FORCE_REBUILD" != "1" ]; then
  echo "Image ${KAMRA_IMAGE}:${KAMRA_TAG} already present — skipping build."
  echo "  (re-run with FORCE_REBUILD=1 to rebuild from ${KAMRA_BRANCH})"
else
  echo "Building ${KAMRA_IMAGE}:${KAMRA_TAG} from ${KAMRA_GIT_URL}@${KAMRA_BRANCH}…"
  echo "  (first build downloads Frappe toolchain — go stretch)"
  docker build \
    -t "${KAMRA_IMAGE}:${KAMRA_TAG}" \
    -f images/layered/Containerfile \
    --build-arg "FRAPPE_PATH=${FRAPPE_PATH}" \
    --build-arg "FRAPPE_BRANCH=${FRAPPE_BRANCH}" \
    --build-arg "CACHE_BUST=${KAMRA_BRANCH}-$(date +%s)" \
    --secret "id=apps_json,src=${APPS_JSON}" \
    . || die "docker build failed — need ~8 GB RAM free and BuildKit enabled"
fi

ENVFILE="$INSTALL_DIR/kamra.env"
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

COMPOSE=(docker compose --project-name kamra --env-file "$ENVFILE"
  -f compose.yaml
  -f overrides/compose.mariadb.yaml
  -f overrides/compose.redis.yaml
  -f overrides/compose.noproxy.yaml)

echo "Starting the stack with local image ${KAMRA_IMAGE}:${KAMRA_TAG}…"
"${COMPOSE[@]}" up -d

echo "Waiting for MariaDB and backend…"
for i in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T backend bench --version >/dev/null 2>&1; then
    break
  fi
  sleep 5
  [ "$i" -eq 60 ] && die "backend did not become ready — check: docker compose -p kamra logs"
done

# Idempotent: skip new-site if sites already exist
SITE_EXISTS=$("${COMPOSE[@]}" exec -T backend bash -lc \
  "ls sites 2>/dev/null | grep -v ^apps\\.txt | grep -v ^assets | grep -v ^common_site_config | head -1" || true)
if [ -z "${SITE_EXISTS//[$'\t\r\n ']/}" ]; then
  echo "Creating site ${SITE_NAME} (this takes a few minutes)…"
  "${COMPOSE[@]}" exec -T backend bench new-site "$SITE_NAME" \
    --mariadb-user-host-login-scope='%' \
    --db-root-password "$DB_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --install-app payments --install-app kamra --no-mariadb-socket
else
  echo "Site already present (${SITE_EXISTS}) — skipping new-site."
fi

echo "First-boot wiring (home → /kamra, admin email, scheduler)…"
"${COMPOSE[@]}" exec -T \
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
green "Stack dir: ${INSTALL_DIR}   env: ${ENVFILE}   apps: ${APPS_JSON}"
green "Update later (rebuild local image + migrate):"
green "  cd ${INSTALL_DIR}/frappe_docker"
green "  DOCKER_BUILDKIT=1 docker build -t ${KAMRA_IMAGE}:${KAMRA_TAG} \\"
green "    -f images/layered/Containerfile \\"
green "    --build-arg FRAPPE_BRANCH=${FRAPPE_BRANCH} \\"
green "    --secret id=apps_json,src=${APPS_JSON} ."
green "  docker compose --project-name kamra --env-file ${ENVFILE} \\"
green "    -f compose.yaml -f overrides/compose.mariadb.yaml \\"
green "    -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml up -d"
green "  docker compose -p kamra exec backend bench --site ${SITE_NAME} migrate"
