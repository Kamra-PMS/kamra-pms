# Hyperscaler marketplaces (AWS · Azure · GCP)

Plan big; ship after Hostinger / DigitalOcean / Linode 1-clicks.

## Two products — never one

| Listing | Type | Who pays | HeyKoala gets |
| --- | --- | --- | --- |
| **Kamra PMS (self-host)** | Free AMI / VM / container 1-click in *their* VPC | EC2 / VM only | Distribution (+ optional affiliate). Same first-boot: site, admin email, password. |
| **Kamra Cloud + HeyKoala** | Paid SaaS (private offers) | Hotel’s AWS / Azure / GCP bill | Hosting + WhatsApp / voice concierge minutes, minus ~3% marketplace fee. |

**Do not** put a paid price on AGPL Kamra software itself.

## Order

1. **AWS Marketplace** — broadest buyers + ISV Accelerate co-sell.
2. **Azure Marketplace** — Microsoft-centric groups.
3. **Google Cloud Marketplace**.

Reuse `ghcr.io/kamra-pms/kamra:latest`; each cloud needs a thin Packer /
Terraform wrapper + listing copy. Legal entity, tax forms, and a security
questionnaire are required before go-live (weeks to months).

## Near-term money

For independents, earn on **VPS affiliates** instead — see
[get-started](https://kamrapms.com/get-started/) (Hostinger %, DigitalOcean
recurring, Linode CPA). Hyperscaler SaaS is the enterprise procurement path.
