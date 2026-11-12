# API stability

Connected apps, AI clients and add-ons build on Kamra's public interfaces.
An update should never break them without warning, so these interfaces are
written down in a contract file and every pull request is checked against
it before it can merge.

## What the contract covers

[`contract.json`](/contract.json) is generated from the code on every docs
build (`docs-site/gen_contract.py`). It lists:

- **MCP tools**: name, the REST method behind it, each input and its type,
  which inputs are required, and the hints a client uses to decide what
  needs approval (`readOnlyHint`, `destructiveHint`, `idempotentHint`).
- **REST methods**: every method behind an MCP tool or granted by a service
  account scope, with its parameters and which of them are optional. The
  read methods connected apps use most also list the keys their response
  carries: `api.get_folio`, `api.folio_invoice`, `api.property_locale`,
  `cashier.list_sessions`, `cashier.session_report` and
  `reports.manager_flash`.
- **Service account scopes**: each scope and the tools and methods it grants.
- **Webhooks**: the envelope every delivery carries, each event, and the
  keys of its `data`.

Response and payload keys are listed by hand in `kamra/contract_keys.py`,
and a test calls each method and fires each event to prove every listed key
is really there. A key that is not listed may still be returned, but it is
not part of the promise.

## What counts as a breaking change

The CI job **Public contract check** compares the contract of a pull request
with the one of the branch it targets and fails on:

- a tool, method, scope or webhook event that is removed or renamed;
- a tool input or method parameter that is removed, or whose type changes;
- a new required input or parameter, or an optional one that becomes
  required;
- a removed response key, webhook payload key or envelope key;
- a scope that grants fewer tools or methods than before.

Additions always pass: a new tool, method, scope or event, a new optional
input, a new key.

## Deprecating something

When a name has to go, keep the old one working (an alias or a fallback) and
list it in `contract-deprecations.json` at the root of the repository:

```json
{
  "deprecations": [
    {
      "item": "tool:old_tool_name",
      "replacement": "new_tool_name",
      "remove_in": "2.10.0"
    }
  ]
}
```

- `item` is the key the check prints for the change, for example
  `tool:check_in`, `method:kamra.api.get_folio:response:balance` or
  `event:folio.posted`. An item also covers everything under it.
- `replacement` says what to use instead.
- `remove_in` is the release the old name goes away in. It has to be at
  least **two minor releases** after the current version: a change made
  during 2.7.x can be removed in 2.9.0 at the earliest.

Run the check yourself before you open a pull request:

```
git worktree add --detach /tmp/kamra-base origin/develop
python3 docs-site/gen_contract.py --root /tmp/kamra-base --out /tmp/base.json
python3 docs-site/gen_contract.py --keep /tmp/base.json --out /tmp/head.json
python3 scripts/contract_check.py /tmp/base.json /tmp/head.json \
  --deprecations contract-deprecations.json
```
