# Self-hosting Kamra

Own your PMS end to end. Ways to install:

| Method | Effort | Best for |
| --- | --- | --- |
| [Hostinger VPS + one command](/self-hosting/hostinger) | Buy a VPS, paste one line | Cheapest path, India / SEA |
| [Docker quickstart](/quickstart) on any VPS | One command, three prompts | DigitalOcean, Linode, AWS, your own box |
| [Bench install](/self-hosting/bench) | Classic Frappe bench | Teams already running Frappe / ERPNext |
| [Frappe Cloud Marketplace](/self-hosting/frappe-cloud) | Point and click | Managed Frappe hosting, no server |
| [Kamra Cloud](https://kamrapms.com/cloud/) | Nothing to run | We host, back up and update it | Every feature is included — there is
no paid edition to upgrade to.

Want company books or HR on the same Frappe site? That is optional —
see [ERPNext and Frappe HR](/self-hosting/erpnext-hr) (Marketplace and
own-server steps).

## Server requirements

| | Minimum | Recommended (20+ rooms, POS) |
| --- | --- | --- |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 40 GB SSD | 80 GB SSD |
| OS | Ubuntu 22.04/24.04 LTS (any Docker-capable Linux) | — |

Measured on our own servers: a full single-property stack (database,
cache, workers, web) idles around 600 MB of RAM — 4 GB leaves comfortable
headroom for busy days. The Docker installer **builds the image on your
server** (20–45 minutes the first time); on boxes under 8 GB it adds a swap
file for the build automatically.

**Also needed:** a domain or subdomain (`pms.yourhotel.com`) pointed at
the server; ports 80/443 open; SSL via Let's Encrypt.

## Typical monthly cost

| Provider | Plan that fits | Price | Guide |
| --- | --- | --- | --- |
| Hostinger | KVM 2 (2 vCPU / 8 GB) | ~₹549/mo | [Guide](/self-hosting/hostinger) |
| DigitalOcean | Basic 4 GB | ~$24/mo | [Guide](/self-hosting/digitalocean) |
| Linode | Shared 4 GB | ~$24/mo | [Guide](/self-hosting/linode) |
| AWS | t3.medium + EBS | ~$30/mo | [Guide](/self-hosting/aws) |

Hyperscaler storefronts (free AMI + paid Kamra Cloud SaaS):
[AWS / Azure / GCP](/self-hosting/marketplace/hyperscalers).

::: tip Rather not run a server?
[Kamra Cloud](https://kamrapms.com/cloud/) is the same software, hosted,
backed up and updated by the team that builds it — from ₹2,999/month
billed annually. You can export everything and move to self-hosting any
time; that's the point of open source.
:::

## After install — production checklist

1. **Create your property** — sign in at `/kamra` as `Administrator` with
   the admin password you chose at install — there is **no default** —
   then open **`/kamra/setup`** (rooms, room types, rates).
2. **Staff users & roles** — Hotel Admin / Front Desk / Revenue / Finance /
   Housekeeping; roles decide what each person sees.
3. **Email** — [set up SMTP](/self-hosting/email) for confirmations,
   invoices and briefings.
4. **Payments** — add gateway keys in the payments app (e.g. Razorpay
   Settings); turn off test mode.
5. **Scheduler** — `install.sh` enables it; night audit runs at 03:00 site
   time and housekeeping SLAs escalate every 15 min.
6. **Backups** — `bench backup --with-files` on cron to off-site storage.
7. **Security** — `developer_mode 0`, strong admin password, HTTPS only.
8. **AI (optional)** — [bring your own model](/ai-and-mcp) or Connect Claude
   over MCP; then optionally Connect HeyKoala WhatsApp from Marketplace.

## Updating (Docker install)

```bash
sudo /opt/kamra/install.sh update
```

That rebuilds the image from the branch recorded in `/opt/kamra/apps.json`
(fetching the latest Kamra code), recreates the containers and runs
`bench migrate` on every site. To switch channel or pin a release, pass
the branch or tag: `sudo KAMRA_BRANCH=v2.6.4 /opt/kamra/install.sh update`.
Expect 10–30 minutes; the running site stays up until the containers are
recreated at the end.

Bench self-host:

```bash
cd frappe-bench/apps/kamra && git pull
bench --site pms.yourhotel.com migrate
bench build && bench restart
```

Run the eval harness after any update — deterministic checks over money,
tax and availability logic:

```bash
bench --site pms.yourhotel.com console
>>> from kamra.scripts.eval_harness import execute; execute()
```
