# DigitalOcean Marketplace 1-Click — Kamra

## Goal

Create Droplet → type **site domain**, **admin email**, **admin password** →
open `https://<ip>/kamra` (or the domain after DNS).

## Vendor steps (HeyKoala)

1. Apply at <https://marketplace.digitalocean.com/vendors>.
2. Build an Ubuntu 24.04 snapshot with Docker + this repo's `deploy/` scripts
   (see [packer.json.example](packer.json.example) and
   [cloud-init.yaml.example](cloud-init.yaml.example)).
3. UDFs (user-defined fields) on the listing:
   - `site_name` (string)
   - `admin_email` (string)
   - `admin_password` (password, min 10)
4. First boot writes `/root/kamra-udf.env` from UDFs and runs `install.sh`.
5. Listing title: **Kamra — open-source hotel PMS**.
6. Create-droplet URL on kamrapms.com **must** use the HeyKoala DigitalOcean
   affiliate / Marketplace vendor link (see website `affiliates.ts`).

## CI

Nightly or release: rebuild the Packer image from
`ghcr.io/kamra-pms/kamra:latest` so the 1-Click stays current. Submit the
snapshot id via the Vendor Portal API.

## Affiliate

Software is free. Hotel pays DigitalOcean. HeyKoala earns **~10% of spend
for 12 months** via the DO affiliate program.
