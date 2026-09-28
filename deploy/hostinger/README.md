# Hostinger — Kamra install

Hostinger has the **strongest affiliate %** for India / SEA hotels and the
weakest official ISV 1-click. Until they accept a VPS template, the path is:

1. Create **KVM 2** (2 vCPU / 8 GB) · **Ubuntu 24.04 with Docker** via the
   Kamra referral link <https://www.hostinger.com/in?REFERRALCODE=kamrapms>
   (buyer saves 20%; same link as the website's `src/data/affiliates.ts`).
2. Point `pms.yourhotel.com` A-record at the VPS IP.
3. hPanel → VPS → **Browser terminal** (or SSH) and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

4. Answer site domain, admin email, admin password.
5. Put TLS in front (`certbot --nginx -d pms.yourhotel.com`) or Hostinger's panel proxy.
6. Open `/kamra/setup`. Update later with `sudo /opt/kamra/install.sh update`.

Hostinger's VPS "templates" catalogue is Hostinger-curated; once Kamra has
traction, apply to get a Kamra template listed so this becomes a true
one-click.

## Affiliate

Hostinger affiliate often **~40%+** of first sale (tiered); Partner program
**~20% new + 10% renewals**. Keep the affiliate ID only in website config
(`affiliates.ts`), never hard-coded in docs partners copy-paste.
