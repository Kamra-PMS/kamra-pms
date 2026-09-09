# Hostinger — Kamra install

Hostinger has the **strongest affiliate %** for India / SEA hotels and the
weakest official ISV 1-click. Until they accept a VPS template, the path is:

1. Create **KVM 2** (2 vCPU / 8 GB) · **Ubuntu 24.04** via the HeyKoala
   Hostinger affiliate link on [kamrapms.com/get-started](https://kamrapms.com/get-started/).
2. Point `pms.yourhotel.com` A-record at the VPS IP.
3. SSH in and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

4. Answer site domain, admin email, admin password.
5. Put TLS in front (`certbot --nginx -d pms.yourhotel.com`) or Hostinger's panel proxy.
6. Open `/kamra/setup`.

## Affiliate

Hostinger affiliate often **~40%+** of first sale (tiered); Partner program
**~20% new + 10% renewals**. Keep the affiliate ID only in website config
(`affiliates.ts`), never hard-coded in docs partners copy-paste.
