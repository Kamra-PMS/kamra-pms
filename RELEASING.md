# Releasing Kamra PMS

The maintainer runbook. Contributors don't need this — see
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Channels

| Channel | Source | Where it goes | When |
|---|---|---|---|
| **nightly** | `develop` | nightly.kamrapms.com, `ghcr.io/kamra-pms/kamra:nightly`, rolling `nightly` prerelease | every night at 03:00 IST, if develop moved and CI is green |
| **stable** | `main` + tag `vX.Y.Z` | GitHub Release, `ghcr.io/kamra-pms/kamra:<tag>` + `:latest`, demo.kamrapms.com, Frappe Cloud Marketplace | when a Release PR is merged |

## The normal release train (monthly, or when a feature set is ready)

1. **Merge the train:** open a PR `develop` → `main` titled
   `chore: release train YYYY-MM`, wait for CI, merge (merge commit, not
   squash — keeps individual Conventional Commits visible to release-please).
2. **Review the Release PR:** release-please opens/updates
   `chore(main): release X.Y.Z` on `main` with the version bump
   (`kamra/__init__.py`) and the CHANGELOG draft. Edit the changelog prose in
   that PR if the auto-generated wording needs polish — hand-curated notes are
   part of the product.
3. **Merge the Release PR.** Automation takes it from there:
   tag `vX.Y.Z` → GitHub Release → Docker image → demo redeploy.
4. **Frappe Cloud Marketplace** (manual, ~2 min): dashboard →
   Apps → kamra → create a release from the new `main` state and submit for
   approval.
5. **Announce:** release thread on discuss.frappe.io; anything else
   (X/LinkedIn) as warranted.

## Hotfix path (stable is broken, develop has moved on)

1. Branch from `main`: `git checkout -b hotfix/<slug> main`.
2. Fix with a `fix:` commit, PR into `main`, merge after CI.
3. Merge the resulting Release PR (PATCH bump) — ships automatically.
4. **Port back:** cherry-pick the fix onto `develop` (or merge `main` into
   `develop`) so the next train doesn't regress it.

## Supported versions

- One stable line at a time (the latest minor). Older minors: upgrade.
- Frappe compatibility: **v16** (see README). When v17 support lands, cut a
  `version-16` maintenance branch from `main` at that point and adopt the
  Frappe-style branch convention — not before.

## Nightly channel notes

- `nightly.yml` refuses to ship if CI on `develop` HEAD isn't green — fix CI
  rather than forcing.
- Force an off-schedule nightly: Actions → Nightly → *Run workflow*.
- nightly.kamrapms.com is disposable; reseed with
  `bench --site nightly.kamrapms.com execute kamra.scripts.seed_demo.execute`.

## Distribution channels checklist (kept current per release)

- **Frappe Cloud Marketplace** — listing tracks `main`; release step 4 above.
- **Docker self-host** — `ghcr.io/kamra-pms/kamra:latest` (and `:nightly`);
  built with frappe_docker's layered Containerfile, so standard
  frappe_docker compose files run it.
- **bench self-host** — `bench get-app https://github.com/Kamra-PMS/kamra-pms`
  (main) then `bench install-app kamra`; guarded by the fresh-install CI job.
- **Demo** — demo.kamrapms.com redeploys automatically on each stable release.

## Marketplace readiness (one-time, then keep true)

- [x] Public repo, AGPL-3.0 `license.txt`
- [x] `pyproject.toml` valid, version dynamic from `kamra/__init__.py`
- [x] `requires-python` floor at or below the Frappe Cloud v16 Python
      (`>=3.10`) — a floor above the bench's interpreter makes pip refuse the
      install during the marketplace build
- [x] `required_apps = ["payments"]` in hooks
- [x] `add_to_apps_screen` entry (logo, `/kamra` route)
- [x] Prebuilt SPA committed under `kamra/public/frontend` (built by
      `frontend/`'s `npm run build`; keep committing the build output —
      marketplace benches don't run npm)
- [x] Root `package.json` build script for Frappe Cloud
- [x] README compatibility table (Kamra `main` releases ↔ Frappe v16)
- [x] Publisher account on frappecloud.com; Marketplace App `kamra` exists
      (public page is Draft / **Not Available** until a release is approved)
- [x] Listing title, summary, logo, Support + Privacy + docs URLs
- [ ] Human review of the latest App Release (Submission Gate is past
      the blocking Fail; app stays In Review until Frappe publishes)
- [x] Offline marketplace install check:
      `python kamra/scripts/marketplace_install_check.py`

## Secrets the pipelines need (repo → Settings → Secrets)

| Secret | Purpose |
|---|---|
| `DEPLOY_HOST` | VPS IP for demo/nightly deploys |
| `DEPLOY_USER` | SSH user (root) |
| `DEPLOY_SSH_KEY` | private key whose pubkey is in the VPS `authorized_keys` |

Deploy scripts themselves live in the private
[`kamra-deploy`](https://github.com/Kamra-PMS/kamra-deploy) repo and are
rsync'd to the VPS at `~/kamra-deploy/`.
