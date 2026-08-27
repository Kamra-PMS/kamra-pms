# Contributing to Kamra PMS

Kamra is AGPL-3.0 and welcomes contributions — code, country packs, docs, bug
reports. This file covers the mechanics; see [`README.md`](README.md) for
install/quickstart and [`docs/`](docs/) for architecture.

## Development setup

Follow the **Quickstart (development)** section in the README. In short:
a Frappe bench, `bench get-app` this repo, `bench new-site` + `install-app`,
and `npm run dev` in `frontend/` for the SPA.

## Branches

- **`develop`** — the integration branch and the *nightly* channel. All PRs
  target `develop` (it's the default branch). nightly.kamrapms.com and the
  `ghcr.io/kamra-pms/kamra:nightly` image are rebuilt from it every night.
- **`main`** — the stable branch. Only release trains (maintainer merges of
  `develop`) and hotfixes land here; the Frappe Cloud Marketplace listing and
  demo.kamrapms.com track its releases.

### Branch naming

One short prefix, kebab-case slug. Prefer these over free-form names
(`property_management`, `azzaxp/…`, `feature/…`):

| Prefix | Use for | Version impact when released |
|---|---|---|
| `feat/<slug>` | New user-facing capability | **MINOR** (`feat:`) |
| `fix/<slug>` | Bug fix on `develop` | **PATCH** (`fix:`) |
| `hotfix/<slug>` | Urgent fix branched from `main` | **PATCH** (`fix:`) |
| `chore/<slug>` | Tooling, CI, deps, housekeeping | none by itself |
| `docs/<slug>` | Docs / listing copy only | none by itself |

Delete the remote branch after the PR merges — leave `main`, `develop`, and
any still-open work only.

See [`RELEASING.md`](RELEASING.md) for the full release process.

## Before you open a PR

- **Frontend:** `cd frontend && npm run build` must pass (typecheck + build).
- **Backend:** if you touched Python, run the eval harness locally —
  `bench --site <site> console`, then
  `from kamra.scripts.eval_harness import execute; execute()` — and confirm
  it still reports all checks passing.
- CI runs both automatically on every PR; a fresh-install check also verifies
  a brand-new site installs cleanly with your change.

## Commit messages

Please use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add occupancy-slab BAR rates
fix: correct GST rounding on split charges
chore: bump frontend deps

BREAKING CHANGE: removes the `Foo` doctype; see CHANGELOG.
```

Pick the prefix carefully — release automation
([release-please](https://github.com/googleapis/release-please)) derives the
next version and the changelog draft from them:

- **`fix:`** — everyday bugfixes and small corrections (PATCH). Prefer this
  whenever the change is not a new capability.
- **`feat:`** — only for real, user-visible additions (MINOR). Do not mark a
  small fix or polish pass as `feat:` just to “feel like a feature”.
- **`chore:` / `docs:` / `ci:` / `test:`** — no version bump by themselves.
- **`BREAKING CHANGE:`** footer (or `feat!:` / `fix!:`) — MAJOR.

## Versioning & releases

Kamra follows [Semantic Versioning](https://semver.org/):

- **MAJOR** — breaks an existing install on `bench migrate` (a doctype is
  removed, a whitelisted API endpoint is removed or its contract changes).
- **MINOR** — new features, additive/backward-compatible doctype changes.
- **PATCH** — fixes with no migration impact.

**Cadence:** land work on `develop` (nightly). Cut a stable release only when
you are ready to ship to the marketplace / demo — typically a monthly train,
or when a feature set is actually ready. Bugfixes can wait on `develop` and
ship together as one PATCH (or ride along in the next MINOR). Do **not** merge
the Release PR for every small merge into `main`; leave it open (it stays a
draft) until you intend to tag and build.

Merging a release train from `develop` into `main` updates the draft Release
PR with the version bump and [`CHANGELOG.md`](CHANGELOG.md) notes; merging
that Release PR is what tags `vX.Y.Z`, publishes GitHub + Docker, and
redeploys demo.kamrapms.com. Full runbook: [`RELEASING.md`](RELEASING.md).

If your change removes or renames anything a self-hoster might depend on
(a doctype, a whitelisted method, a config key), call it out explicitly under
a `### Removed (⚠️ breaking)` heading in the changelog entry — that's what
decides the next version is a MAJOR bump.

## Country packs

Localization lives behind the `kamra_localization` hook
(`kamra/localization/`); India ships as the reference pack. A new country
pack implements the same interface (tax calculation, invoice context, locale)
without touching the core. See `kamra/localization/india.py` for the shape.

## Code of conduct

Be respectful, assume good faith, keep discussion technical. Report abuse to
hello@kamrapms.com.
