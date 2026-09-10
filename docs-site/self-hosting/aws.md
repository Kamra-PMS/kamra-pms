# Self-hosting on AWS

For a single hotel, prefer [Hostinger](/self-hosting/hostinger) or
[DigitalOcean](/self-hosting/digitalocean). Use AWS when the property (or
group) already lives in an AWS account — or when buying through
[AWS Marketplace](/self-hosting/marketplace/hyperscalers) later.

## Manual EC2

### 1. Create the server

EC2 → Ubuntu 24.04 → **t3.medium** (2 vCPU / 4 GB) → 40 GB gp3 → security
group **22, 80, 443** → Elastic IP.

### 2. DNS

**A record** `pms.yourhotel.com` → Elastic IP.

### 3. Install

```bash
ssh ubuntu@<server-ip>   # or root, depending on AMI
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

Site domain, admin email, admin password — no default.

### 4. TLS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d pms.yourhotel.com
```

Then `/kamra/setup`. See [Quickstart](/quickstart).

## Marketplace (planned)

Free **Kamra PMS** AMI (self-host in your VPC) and a paid **Kamra Cloud +
HeyKoala** SaaS listing (hotel pays on the AWS invoice). Details:
[Hyperscaler marketplaces](/self-hosting/marketplace/hyperscalers).
