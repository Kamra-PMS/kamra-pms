# Self-host install troubleshooting

## `unauthorized` when pulling `ghcr.io/kamra-pms/kamra`

**Symptom**

```text
Head "https://ghcr.io/v2/kamra-pms/kamra/manifests/latest": unauthorized
```

**Cause**

The prebuilt image package is **private** for now, and this server is not
logged in to `ghcr.io` (or its token lacks `read:packages`). Pull mode
(`KAMRA_PULL=1` / `KAMRA_TAG=…`) and `deploy/compose/quickstart.yaml` need
registry access; the current installer then falls back to building.

**Fix**

Either log in (`echo "$TOKEN" | docker login ghcr.io -u <user>
--password-stdin`) and re-run, or use the default [`install.sh`](install.sh)
from `main` without `KAMRA_PULL` — it **builds** `kamra:local` on the
server (`PULL_POLICY=never`).

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

**Requirements**

- ~8 GB RAM, 40 GB disk (4 vCPU helps)
- First run often **20–45 minutes** (Frappe + payments + kamra build)
- Docker Engine ≥ 24, Compose v2

Then open `http://<server-ip>:8080/kamra` → `/kamra/setup`.

**Alternatives (no GHCR)**

- **Bench:** see [docs/self-hosting.md](../docs/self-hosting.md)
- **Managed:** [Frappe Cloud Marketplace](https://cloud.frappe.io/marketplace/apps/kamra)

---

## Copy-paste reply for GitHub reports

> Thanks for reporting this — the `unauthorized` error happens because an older public installer tried to pull a private Docker image we don’t offer for self-host.
>
> We’ve updated the installer to **build Kamra on your server** instead. Please use a VPS with about **8 GB RAM** (first install can take **20–45 minutes**), then run:
>
> ```bash
> curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
> ```
>
> If you’d rather not build Docker locally, you can install via **bench** or **Frappe Cloud** (links in our [self-hosting docs](https://github.com/Kamra-PMS/kamra-pms/blob/main/docs/self-hosting.md)). Sorry for the confusion.

---

## `ERPNEXT_VERSION` warnings during compose

Harmless noise from upstream `frappe_docker` when `ERPNEXT_VERSION` is unset.
Current `install.sh` sets `ERPNEXT_VERSION` in `kamra.env` when using a local
image tag.

---

## Upgrading cache/queue from Redis 8.x to Valkey

Docker defaults now use `valkey/valkey:8-alpine` for `redis-cache` /
`redis-queue` (service names and `redis://` bench URLs are unchanged).

**Greenfield installs:** no action.

**Existing installs that already ran `redis:7.4+` / `redis:8.x`:** Valkey
cannot load Redis CE 7.4+ RDB files. Before recreating those containers:

1. Stop workers / take a short maintenance window
   (`docker compose -p kamra stop` or equivalent).
2. Accept that the job queue will rebuild empty — drain or discard
   `redis-queue-data` (`docker volume rm …_redis-queue-data` after
   compose down, or remove `/data/dump.rdb` in that volume).
3. Pull/start with the new compose (or re-run `install.sh update`), which
   rewrites the upstream redis override to Valkey.

`redis-cache` is ephemeral and needs no migration. App data lives in
MariaDB, not in the cache/queue volumes.
