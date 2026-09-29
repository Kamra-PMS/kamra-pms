# Self-host install troubleshooting

## `unauthorized` when pulling `ghcr.io/kamra-pms/kamra`

**Symptom**

```text
Head "https://ghcr.io/v2/kamra-pms/kamra/manifests/latest": unauthorized
```

**Cause**

Older installers tried to pull a **private** GHCR image. Kamra does not
publish a public registry image for random self-hosters (GHCR is for
Kamra-operated demo/nightly only).

**Fix**

Use a current [`install.sh`](install.sh) from `main` — it **builds**
`kamra:local` on the server (`PULL_POLICY=never`).

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
