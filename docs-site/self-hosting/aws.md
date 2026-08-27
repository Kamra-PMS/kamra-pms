# Self-hosting on AWS

## 1. Create the server

In EC2, **Launch instance** → Ubuntu Server 24.04 → **t3.medium** (2 vCPU / 4 GB, ~$30/mo with EBS) → 40 GB gp3 volume → a security group allowing ports **22, 80, 443** → attach an **Elastic IP** so the address survives restarts.

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
