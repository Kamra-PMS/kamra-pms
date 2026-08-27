# Self-hosting Kamra

Own your PMS end to end. Two supported paths: **Docker (recommended,
see the [Quickstart](/quickstart))** or a classic
[bench install](/self-hosting/bench). Every feature is included — there is
no paid edition to upgrade to.

## Server requirements

| | Minimum | Recommended (20+ rooms, POS) |
| --- | --- | --- |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 40 GB SSD | 80 GB SSD |
| OS | Ubuntu 22.04/24.04 LTS (any Docker-capable Linux) | — |

Measured on our own servers: a full single-property stack (database,
cache, workers, web) idles around 600 MB of RAM — 4 GB leaves comfortable
headroom for busy days and updates.

**Also needed:** a domain or subdomain (`pms.yourhotel.com`) pointed at
the server; ports 80/443 open; SSL via Let's Encrypt.

## Typical monthly cost

| Provider | Plan that fits | Price | Guide |
| --- | --- | --- | --- |
| Hostinger | KVM 2 (2 vCPU / 8 GB) | ~₹549/mo | [Guide](/self-hosting/hostinger) |
| DigitalOcean | Basic 4 GB | ~$24/mo | [Guide](/self-hosting/digitalocean) |
| Linode | Shared 4 GB | ~$24/mo | [Guide](/self-hosting/linode) |
| AWS | t3.medium + EBS | ~$30/mo | [Guide](/self-hosting/aws) |

::: tip Rather not run a server?
[Kamra Cloud](https://kamrapms.com/#cloud) is the same software, hosted,
backed up and updated by the team that builds it — from ₹2,999/month
billed annually. You can export everything and move to self-hosting any
time; that's the point of open source.
:::

## After install — production checklist

1. **Create your property** — sign in at `/kamra` as `Administrator` (or
   `admin@example.com`) with the `--admin-password` you chose — there is
   no default — then Admin → New Property, rooms, room types and rates.
2. **Staff users & roles** — Hotel Admin / Front Desk / Revenue / Finance /
   Housekeeping; roles decide what each person sees.
3. **Email** — [set up SMTP](/self-hosting/email) for confirmations,
   invoices and briefings.
4. **Payments** — add gateway keys in the payments app (e.g. Razorpay
   Settings); turn off test mode.
5. **Scheduler** — `bench --site <site> enable-scheduler`; the night audit
   runs at 03:00 site time and housekeeping SLAs escalate every 15 min.
6. **Backups** — `bench backup --with-files` on cron to off-site storage.
7. **Security** — `developer_mode 0`, strong admin password, HTTPS only.
8. **AI (optional)** — [connect Claude over MCP](/ai-and-mcp) or enable
   the in-app copilot with your own key.

## Updating

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
