# Kamra deploy — self-host

By default the installer builds Frappe + payments + kamra **on the hotel's
VPS**. With access to the prebuilt image `ghcr.io/kamra-pms/kamra` it can
pull it instead (`KAMRA_PULL=1`) — see [Pull mode](#pull-mode). The
package is private for now, so pulling needs `docker login ghcr.io` with a
`read:packages` token.

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

You will be asked for:

1. **Site domain** — `pms.yourhotel.com`
2. **Admin email**
3. **Admin password** (min 10 characters; there is no default)

First install typically takes **20–45 minutes** (image build). Minimum
**2 vCPU · 4 GB RAM · 40 GB disk**; under 8 GB the installer adds a swap
file (`/swapfile-kamra`) so the build doesn't run out of memory. Then open
`/kamra/setup` and create the property.

## Modes

| Command | What it does |
| --- | --- |
| `install.sh` | Install. Safe to re-run: keeps the DB password in `kamra.env` and skips `new-site` if a site exists. |
| `/opt/kamra/install.sh update` | `bench --site all backup --with-files` first (**aborts if it fails**), then rebuild the image from `apps.json` (fresh `CACHE_BUST`) or pull the newest tag of the recorded channel, recreate containers, `bench --site all migrate`. `KAMRA_BRANCH=vX.Y.Z` (build) / `KAMRA_TAG=vX.Y.Z` (pull) pins a release. |
| `install.sh build` | Build the image only — used by Packer to bake 1-Click snapshots so first boot skips the build. |
| `install.sh pull` | Pull + pin the image only — the snapshot step once the image is public. |

## Pull mode

```bash
echo "$TOKEN" | docker login ghcr.io -u <github-user> --password-stdin   # until the package is public
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | KAMRA_PULL=1 bash
```

- Pulls `ghcr.io/kamra-pms/kamra:stable`, reads the Kamra version inside
  it, checks `:vX.Y.Z` is the same image, and runs that pinned tag
  (`PULL_POLICY=missing`, so restarts never re-pull). No buildx, no swap.
- `KAMRA_TAG=v2.6.16` pins a release; `KAMRA_TAG=nightly` follows nightly.
- `/opt/kamra/image.env` records mode / channel / pinned tag; `update`
  follows the channel (`stable` → the newest release).
- A refused pull (private package, no login, wrong CPU) prints why and
  falls back to building (`KAMRA_PULL_FALLBACK=0` fails instead). During
  `update` it aborts without touching anything.
- Flip the default to pull later: `DEFAULT_MODE=pull` in `install.sh`.

Tags: `stable` (newest release), `vX.Y.Z` (pin in production), `nightly`
(testing), `latest` (alias of `stable`). The image is linux/amd64 and holds
only public code — Frappe, payments, Kamra — no site data or secrets
(those live in Docker volumes and `kamra.env` on your server). Old tags
are pruned weekly by `.github/workflows/ghcr-retention.yml` (keeps the 3
newest releases + `stable`/`latest`/`nightly` and the manifests they
reference).

## Try it locally

[`compose/quickstart.yaml`](compose/quickstart.yaml) runs the prebuilt
image + MariaDB + Redis and creates a site — `docker compose -f
quickstart.yaml up -d`, then <http://localhost:8080/kamra>. It needs
`KAMRA_ADMIN_PASSWORD` and `KAMRA_DB_PASSWORD` in the environment (no
default secrets) and, while the package is private, `docker login
ghcr.io`. Evaluation only.

Hit `unauthorized` on GHCR? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and
the copy-paste reply for GitHub reports.

## What gets built

| Piece | Source |
| --- | --- |
| Base | [frappe_docker](https://github.com/frappe/frappe_docker) layered Containerfile |
| Apps | `frappe/payments` + `Kamra-PMS/kamra-pms` (`main` by default) |
| Local tag | `kamra:local` (`PULL_POLICY=never`) |

Overrides:

| Env | Default | Purpose |
| --- | --- | --- |
| `KAMRA_BRANCH` | `main` | Git branch/tag of kamra-pms to bake in |
| `KAMRA_GIT_URL` | `https://github.com/Kamra-PMS/kamra-pms` | Fork URL |
| `KAMRA_PULL` | unset | `1` = pull the prebuilt image instead of building |
| `KAMRA_BUILD` | unset | `1` = build (wins over `KAMRA_PULL` / `KAMRA_TAG`) |
| `KAMRA_TAG` | `stable` (pull) / `local` (build) | Tag to pull (setting it implies pull mode) |
| `KAMRA_IMAGE` | `ghcr.io/kamra-pms/kamra` / `kamra` | Image name (pull / build) |
| `KAMRA_APPS_JSON` | unset | Custom `apps.json` for build mode (forks, extra apps) |
| `KAMRA_PULL_FALLBACK` | `1` | `0` = fail instead of building when a pull is refused |
| `FORCE_REBUILD` | `0` | Set `1` to rebuild even if the tag exists |
| `FRAPPE_BRANCH` | `version-16` | Frappe branch for the layered build |
| `FRAPPE_DOCKER_REF` | pinned SHA | frappe_docker commit; bump only after `deploy-smoke` CI passes |

## Layout after install

```
/opt/kamra/
  install.sh          # copy of the installer, for `install.sh update`
  kamra.env           # compose secrets (DB password, site header, image), mode 600
  image.env           # build|pull, image, channel, pinned tag (not secret)
  apps.json           # apps + branch baked into the local image (build mode)
  frappe_docker/      # upstream compose files (MariaDB + Redis + noproxy)
```

## One-click clouds

| Cloud | Path |
| --- | --- |
| [DigitalOcean](digitalocean/) | Marketplace 1-Click (Packer + cloud-init) |
| [Linode / Akamai](linode/) | Marketplace One-Click (StackScript) |
| [Hostinger](hostinger/) | Affiliate VPS + one paste of `install.sh` |

The DigitalOcean Packer template bakes the image with `install.sh build`,
so first boot only creates the site. The Linode StackScript still builds on
first boot (20–45 minutes).

## Hyperscalers

Free self-host AMI/VM listings are planned — see [docs](../docs-site/self-hosting/marketplace/hyperscalers.md). Do not put a price on AGPL Kamra itself.

## Published images

CI publishes `ghcr.io/kamra-pms/kamra:{vX.Y.Z,stable,latest}` on every
release (`release.yml`; `stable`/`latest` move only for the newest
release) and `:nightly` (`nightly.yml`). The package is private for now —
pull mode needs a `docker login ghcr.io`; the default install builds.
