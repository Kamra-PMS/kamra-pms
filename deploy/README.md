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

First install typically takes **20–45 minutes** (image build). Prefer
**4 vCPU · 8 GB RAM · 40 GB disk**. Then open `/kamra/setup` and create
the property.

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

## Layout after install

```
/opt/kamra/
  kamra.env           # compose secrets (DB password, site header)
  apps.json           # baked into the local image
  frappe_docker/      # upstream compose files (MariaDB + Redis + noproxy)
```

## One-click clouds

| Cloud | Path |
| --- | --- |
| [DigitalOcean](digitalocean/) | Marketplace 1-Click (Packer + cloud-init) |
| [Linode / Akamai](linode/) | Marketplace One-Click (StackScript) |
| [Hostinger](hostinger/) | Affiliate VPS + one paste of `install.sh` |

First boot runs the same build — expect a long first boot, not a quick pull.

## Hyperscalers

Free self-host AMI/VM listings and paid **Kamra Cloud + HeyKoala** SaaS listings are planned — see [docs](../docs-site/self-hosting/marketplace/hyperscalers.md). Do not put a price on AGPL Kamra itself.

## Kamra-operated images (not for public install)

CI still publishes `ghcr.io/kamra-pms/kamra:{latest,nightly}` for
demo.kamrapms.com / nightly.kamrapms.com. Those packages stay **private**.
Self-hosters should always use `install.sh` (local build).
