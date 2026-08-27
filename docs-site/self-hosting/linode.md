# Self-hosting on Linode (Akamai)

## 1. Create the server

Create a **Linode** → Ubuntu 24.04 → **Shared CPU / Linode 4 GB** (~$24/mo) → region nearest your hotel → root password + SSH key.

## 2. Point your domain

Add an **A record** for `pms.yourhotel.com` → the server's IP at your
DNS provider. (If you use Cloudflare, set it to *DNS only* while issuing
the SSL certificate.)

## 3. Install Docker

```bash
ssh root@<server-ip>
curl -fsSL https://get.docker.com | sh
```

## 4. Install Kamra

From here it's identical everywhere — follow the
[Quickstart](/quickstart): build the image with Kamra in `apps.json`,
bring the compose stack up, create your site, enable the scheduler.

## 5. SSL

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d pms.yourhotel.com
```

Then sign in at `/kamra` as `Administrator` or `admin@example.com` with
the `--admin-password` from the Quickstart — there is no default — and
work through the [production checklist](/self-hosting/#after-install-production-checklist).
