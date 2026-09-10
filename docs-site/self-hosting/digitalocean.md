# Self-hosting on DigitalOcean

## Marketplace 1-Click (preferred)

When the Kamra listing is live on the
[DigitalOcean Marketplace](https://marketplace.digitalocean.com/):

1. Create Droplet → search **Kamra**.
2. Enter **site domain**, **admin email**, **admin password**.
3. Open `/kamra` → `/kamra/setup`.

Use the create link on [kamrapms.com/get-started](https://kamrapms.com/get-started/)
so DigitalOcean credits the HeyKoala affiliate (~10% of spend for 12 months).

Vendor / Packer notes live in the repo at `deploy/digitalocean/`.

## Manual (same result)

### 1. Create the server

**Droplet** → Ubuntu 24.04 → **Basic / 4 GB / 2 vCPU** (~$24/mo) → region near
the hotel → SSH key.

### 2. Point your domain

**A record** for `pms.yourhotel.com` → droplet IP.

### 3. Install

```bash
ssh root@<server-ip>
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

Three prompts: site domain, admin email, admin password. No default password.

### 4. TLS

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d pms.yourhotel.com
```

Then `/kamra/setup`. See [Quickstart](/quickstart).
