#!/bin/bash
# Linode / Akamai Marketplace One-Click — Kamra StackScript stub.
#
# Submit via https://www.linode.com/marketplace/app-partners/ with Ansible
# playbooks per https://github.com/linode-solutions/marketplace-apps
#
# UDF fields (Linode Marketplace convention):
# <UDF name="site_name" label="Site domain" example="pms.yourhotel.com" />
# <UDF name="admin_email" label="Admin email" example="you@yourhotel.com" />
# <UDF name="admin_password" label="Admin password" />
# <UDF name="soa_email_address" label="Let's Encrypt email" default="" />

set -euo pipefail
exec > >(tee -a /var/log/kamra-stackscript.log) 2>&1

export SITE_NAME="${SITE_NAME:-}"
export ADMIN_EMAIL="${ADMIN_EMAIL:-}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
export LETSENCRYPT_EMAIL="${soa_email_address:-$ADMIN_EMAIL}"

apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y curl git ca-certificates
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh \
  -o /tmp/kamra-install.sh
chmod +x /tmp/kamra-install.sh
bash /tmp/kamra-install.sh

unset ADMIN_PASSWORD
echo "Kamra Linode One-Click finished. Open http://$(hostname -I | awk '{print $1}'):8080/kamra"
