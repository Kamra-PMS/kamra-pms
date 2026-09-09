## What & why

<!-- One or two sentences. Link the issue if there is one: Fixes #123 -->

## Checklist

- [ ] PR targets **`develop`** (not `main`)
- [ ] Title / commits follow [Conventional Commits](https://www.conventionalcommits.org/)
      (`feat:` / `fix:` / `docs:` / `chore:` …) — this drives the changelog.
      Releases default to **PATCH** (`2.6.x`); a `feat:` commit does **not**
      auto-bump to the next minor. See [`RELEASING.md`](../RELEASING.md).
- [ ] `cd frontend && npm run build` passes (if frontend touched; commit the
      regenerated `kamra/public/frontend` output)
- [ ] Eval harness still green (if Python touched):
      `from kamra.scripts.eval_harness import execute; execute()`
- [ ] Anything removed/renamed that a self-hoster could depend on (doctype,
      whitelisted method, config key) is called out below as **breaking**

## Breaking changes

<!-- "None" or the list -->
