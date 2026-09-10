# Kamra deploy — WordPress-easy self-host

Pull the published image. Do **not** compile Frappe on the hotel's VPS.

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

You will be asked for:

1. **Site domain** — `pms.yourhotel.com`
2. **Admin email**
3. **Admin password** (min 10 characters; there is no default)

Then open `/kamra/setup` and create the property.

## Image

| Tag | Channel |
| --- | --- |
| `ghcr.io/kamra-pms/kamra:latest` | Stable (`main`) |
| `ghcr.io/kamra-pms/kamra:nightly` | Nightly (`develop`) |
| `ghcr.io/kamra-pms/kamra:vX.Y.Z` | Release pin |

## Layout after install

```
/opt/kamra/
  kamra.env           # compose secrets (DB password, site header)
  frappe_docker/      # upstream compose files (MariaDB + Redis + noproxy)
```

## One-click clouds

| Cloud | Path |
| --- | --- |
| [DigitalOcean](digitalocean/) | Marketplace 1-Click (Packer + cloud-init) |
| [Linode / Akamai](linode/) | Marketplace One-Click (StackScript) |
| [Hostinger](hostinger/) | Affiliate VPS + one paste of `install.sh` |

## Hyperscalers

Free self-host AMI/VM listings and paid **Kamra Cloud + HeyKoala** SaaS listings are planned — see [docs](../docs-site/self-hosting/marketplace/hyperscalers.md). Do not put a price on AGPL Kamra itself.

## Developers

To build the image from source (CI / contributors), use the old
`frappe_docker` layered Containerfile with `apps.json`. That path is for
developers, not hoteliers — see the docs site “Build from source” note.
