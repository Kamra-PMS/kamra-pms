# Kamra deploy — self-host (build on your server)

The installer builds Frappe + payments + kamra **on the hotel's VPS**.
It does **not** pull from `ghcr.io` (that registry stays private for Kamra's
own demo / nightly hosts, so public installers don't burn GHCR bandwidth).

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
| `/opt/kamra/install.sh update` | Rebuild the image from `apps.json` (fresh `CACHE_BUST`, so new Kamra code is fetched), recreate containers, `bench --site all migrate`. `KAMRA_BRANCH=v2.6.4` switches branch/tag. |
| `install.sh build` | Build the image only — used by Packer to bake 1-Click snapshots so first boot skips the build. |

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
| `KAMRA_IMAGE` / `KAMRA_TAG` | `kamra` / `local` | Local image name |
| `FORCE_REBUILD` | `0` | Set `1` to rebuild even if the tag exists |
| `FRAPPE_BRANCH` | `version-16` | Frappe branch for the layered build |
| `FRAPPE_DOCKER_REF` | pinned SHA | frappe_docker commit; bump only after `deploy-smoke` CI passes |

## Layout after install

```
/opt/kamra/
  install.sh          # copy of the installer, for `install.sh update`
  kamra.env           # compose secrets (DB password, site header), mode 600
  apps.json           # apps + branch baked into the local image
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

## Kamra-operated images (not for public install)

CI still publishes `ghcr.io/kamra-pms/kamra:{latest,nightly}` for
demo.kamrapms.com / nightly.kamrapms.com. Those packages stay **private**.
Self-hosters should always use `install.sh` (local build).
