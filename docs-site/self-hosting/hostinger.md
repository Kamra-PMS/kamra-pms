# Self-hosting on Hostinger

Best path for India / Southeast Asia on a cheap VPS. Software stays free;
Hostinger bills the VPS. Use **our referral link** so you save **20%** -
and so the referral helps keep Kamra afloat.

<p>
  <a href="https://www.hostinger.com/in?REFERRALCODE=kamrapms" rel="sponsored noopener" target="_blank">
    <img src="/img/hostinger/Badge_brand_light.svg" alt="Hostinger Partner" width="280" height="105" />
  </a>
</p>

## 1. Create the server

1. Open Hostinger with the Kamra referral link:
   **[hostinger.com/in?REFERRALCODE=kamrapms](https://www.hostinger.com/in?REFERRALCODE=kamrapms)**
   (or enter coupon **`KAMRAPMS`** at checkout).
2. You save **20%**. Using our link is a direct way to support the open-source
   project - it helps keep Kamra afloat.
3. Go to **VPS** and pick **KVM 2** (2 vCPU / 8 GB / ~₹549/mo). For the
   operating system choose **Ubuntu 24.04 with Docker** (plain Ubuntu 24.04
   also works - the installer adds Docker). Set a root password or SSH key
   and note the IP.

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
There is no default password. The installer builds Kamra on the VPS -
allow 20-45 minutes the first time.

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
