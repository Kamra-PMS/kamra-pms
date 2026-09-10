# Self-hosting on Linode (Akamai)

## Marketplace One-Click (preferred)

When Kamra is listed on the
[Akamai / Linode Marketplace](https://www.linode.com/marketplace/):

1. Deploy **Kamra**.
2. Enter **site domain**, **admin email**, **admin password**.
3. Open `/kamra` → `/kamra/setup`.

Use the button on [kamrapms.com/get-started](https://kamrapms.com/get-started/)
for the HeyKoala Impact / affiliate link (~$100 CPA when terms are met).

StackScript notes: `deploy/linode/` in the Kamra repo.

## Manual

### 1. Create the server

**Linode** → Ubuntu 24.04 → **Shared CPU / 4 GB** (~$24/mo) → region + SSH key.

### 2. DNS

**A record** `pms.yourhotel.com` → Linode IP.

### 3. Install

```bash
ssh root@<server-ip>
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

Site domain, admin email, admin password — no default.

### 4. TLS

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d pms.yourhotel.com
```

Then `/kamra/setup`. See [Quickstart](/quickstart).
