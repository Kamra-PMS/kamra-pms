# Self-hosting on Hostinger

Best path for India / Southeast Asia on a cheap VPS. Create the server with
our affiliate link when you can — software stays free; Hostinger bills the VPS.

## 1. Create the server

Use the **Hostinger** button on [kamrapms.com/get-started](https://kamrapms.com/get-started/)
(it credits the Kamra referral at no cost to you), then pick **KVM 2**
(2 vCPU / 8 GB / ~₹549/mo). For the operating system choose
**Ubuntu 24.04 with Docker** (plain Ubuntu 24.04 also works — the installer
adds Docker). Set a root password or SSH key and note the IP.

## 2. Point your domain

**A record** for `pms.yourhotel.com` → the server IP. (Cloudflare: DNS only
while issuing SSL.)

## 3. Install Kamra (one paste)

In hPanel open the VPS → **Browser terminal** (or `ssh root@<server-ip>`)
and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

Answer three prompts: **site domain**, **admin email**, **admin password**.
There is no default password. The installer builds Kamra on the VPS —
allow 20–45 minutes the first time.

## 4. TLS + sign in

Put nginx (or Hostinger's proxy) in front of port `8080`, then:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d pms.yourhotel.com
```

Open `https://pms.yourhotel.com/kamra`, sign in as **Administrator** with the
password you set, then **`/kamra/setup`**.

Updating later: `sudo /opt/kamra/install.sh update`.

Full detail: [Quickstart](/quickstart) · [production checklist](/self-hosting/#after-install-production-checklist).
