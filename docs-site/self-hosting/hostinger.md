# Self-hosting on Hostinger

Best path for India / Southeast Asia on a cheap VPS. Create the server with
our affiliate link when you can — software stays free; Hostinger bills the VPS.

## 1. Create the server

In [hPanel](https://hpanel.hostinger.com) → VPS → **KVM 2** (2 vCPU / 8 GB /
~₹549/mo) → **Ubuntu 24.04** → set a root password or SSH key. Note the IP.

Prefer the button on [kamrapms.com/get-started](https://kamrapms.com/get-started/)
so Hostinger credits the Kamra / HeyKoala referral.

## 2. Point your domain

**A record** for `pms.yourhotel.com` → the server IP. (Cloudflare: DNS only
while issuing SSL.)

## 3. Install Kamra (one paste)

```bash
ssh root@<server-ip>
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

Answer three prompts: **site domain**, **admin email**, **admin password**.
There is no default password.

## 4. TLS + sign in

Put nginx (or Hostinger's proxy) in front of port `8080`, then:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d pms.yourhotel.com
```

Open `https://pms.yourhotel.com/kamra`, sign in as **Administrator** with the
password you set, then **`/kamra/setup`**.

Full detail: [Quickstart](/quickstart) · [production checklist](/self-hosting/#after-install-production-checklist).
