#!/usr/bin/env python3
"""Generate the REST API reference + Postman collection from the source.

Walks the whitelisted functions in kamra's API modules (pure ast - no
frappe import needed) and emits:

  - api-reference.md                      the docs page
  - public/kamra.postman_collection.json  Postman v2.1, with {{base_url}},
                                          {{api_key}}, {{api_secret}} vars

Run from docs-site/:  python3 gen_api.py
Keep this in sync by re-running it whenever endpoints change; CI-friendly
(deterministic output).
"""

import ast
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "kamra")

# module -> (Postman folder, note)
MODULES = [
    ("api", "Core (front desk, folios, guests, rooms)", ""),
    ("pos", "Restaurant POS & kitchen", ""),
    ("laundry", "Laundry (housekeeping)", ""),
    ("migrate", "Migration (CSV import)", ""),
    ("crs", "Central reservations (chain)", ""),
    ("dashboards", "Dashboards", ""),
    ("reports", "Reports", ""),
    ("agents_api", "Activity ledger", ""),
    ("public_api", "Public (no auth - booking page, QR menu)",
     "These are allow_guest endpoints: no token needed, rate-limited."),
]

SAMPLE = {
    "property": "Your Property",
    "room_type": "Your Property-DLX",
    "room": "Your Property-101",
    "reservation": "RES-2026-00001",
    "folio": "FOLIO-2026-00001",
    "guest": "G-00001",
    "guest_name": "A. Guest",
    "full_name": "A. Guest",
    "outlet": "Your Property-Restaurant",
    "order": "ORD-2026-00001",
    "check_in_date": "2026-08-01",
    "check_out_date": "2026-08-03",
    "from_date": "2026-08-01",
    "to_date": "2026-08-31",
    "start_date": "2026-08-01",
    "end_date": "2026-08-31",
    "date": "2026-08-01",
    "business_date": "2026-08-01",
    "email": "guest@example.com",
    "phone": "+91 90000 00000",
    "amount": 1000,
    "adults": 2,
    "children": 0,
}


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def decorators(fn):
    """(is_whitelisted, allow_guest, methods, roles)"""
    wl = guest = False
    methods, roles = ["GET", "POST"], []
    for d in fn.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        name = ast.unparse(target)
        if name.endswith("whitelist"):
            wl = True
            if isinstance(d, ast.Call):
                for kw in d.keywords:
                    if kw.arg == "allow_guest" and literal(kw.value):
                        guest = True
                    if kw.arg == "methods":
                        methods = literal(kw.value) or methods
        elif name.endswith("require_roles") and isinstance(d, ast.Call):
            roles = [literal(a) for a in d.args if literal(a)]
        elif name.endswith("require_it_admin"):
            roles = ["System Manager", "Administrator"]
    return wl, guest, methods, roles


def params(fn):
    """[(name, default-or-None, required)]"""
    args = [a for a in fn.args.args if a.arg not in ("self", "cls")]
    defaults = fn.args.defaults
    pad = [None] * (len(args) - len(defaults))
    out = []
    for a, d in zip(args, pad + list(defaults)):
        default = None if d is None else ast.unparse(d)
        out.append((a.arg, default, d is None))
    return out


def sample_value(name, default, required):
    if name in SAMPLE:
        return SAMPLE[name]
    if default not in (None, "None"):
        try:
            return ast.literal_eval(default)
        except Exception:
            return default
    if required:
        return f"<{name}>"
    return None


def collect():
    modules = []
    for mod, folder, note in MODULES:
        path = os.path.join(APP, f"{mod}.py")
        tree = ast.parse(open(path).read())
        eps = []
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            wl, guest, methods, roles = decorators(node)
            if not wl or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node) or ""
            eps.append({
                "module": mod, "name": node.name, "guest": guest,
                "method": "POST" if methods == ["POST"] else "GET/POST",
                "roles": roles, "doc": doc.strip(),
                "params": params(node),
            })
        modules.append({"module": mod, "folder": folder, "note": note,
                        "endpoints": eps})
    return modules


def esc(text):
    """VitePress compiles markdown as Vue templates: raw `<placeholder>` and
    `{{ }}` in prose break the compiler. Escape them; code spans stay valid
    because we escape the raw chars, not backticked content semantics."""
    text = re.sub(r"<(?=[^`>]*>)", "&lt;", text)
    text = text.replace("{{", "&#123;&#123;")
    return text


def write_markdown(modules):
    total = sum(len(m["endpoints"]) for m in modules)
    out = [f"""---
outline: 2
---

# REST API reference

Every endpoint below is a whitelisted function — the same governed layer
the UI and the AI use. **{total} endpoints**, generated from the source
(`docs-site/gen_api.py`), so this page always matches the code.

## Calling convention

```
POST https://<your-kamra>/api/method/kamra.<module>.<function>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

- Get keys from **Copilot → Connect** (per-user, role-scoped) or the
  dedicated agent user for services.
- Responses: `{{"message": <return value>}}`. Errors are HTTP 4xx with a
  readable reason.
- **Try it in Postman:** [download the collection](/kamra.postman_collection.json),
  set `base_url`, `api_key` and `api_secret` collection variables, go.
- Endpoints marked **public** are `allow_guest` (no token; rate-limited).
"""]
    for m in modules:
        out.append(f"\n## {m['folder']}\n")
        if m["note"]:
            out.append(f"> {m['note']}\n")
        for e in m["endpoints"]:
            badge = " <Badge type='tip' text='public' />" if e["guest"] else ""
            out.append(f"### `kamra.{e['module']}.{e['name']}`{badge}\n")
            meta = [f"**{e['method']}**"]
            if e["roles"]:
                meta.append("roles: " + ", ".join(f"`{r}`" for r in e["roles"]))
            out.append(" · ".join(meta) + "\n")
            if e["doc"]:
                out.append(esc(e["doc"]) + "\n")
            if e["params"]:
                out.append("| Param | Required | Default |")
                out.append("| --- | --- | --- |")
                for n, d, req in e["params"]:
                    out.append(f"| `{n}` | {'yes' if req else 'no'} | "
                               f"{'' if d in (None,) else f'`{d}`'} |")
                out.append("")
    open(os.path.join(HERE, "api-reference.md"), "w").write("\n".join(out))
    return total


def write_postman(modules):
    items = []
    for m in modules:
        folder = {"name": m["folder"], "item": []}
        for e in m["endpoints"]:
            body = {n: sample_value(n, d, req) for n, d, req in e["params"]}
            body = {k: v for k, v in body.items() if v is not None}
            req = {
                "name": e["name"],
                "request": {
                    "method": "POST",
                    "header": [
                        {"key": "Content-Type", "value": "application/json"}]
                    + ([] if e["guest"] else [
                        {"key": "Authorization",
                         "value": "token {{api_key}}:{{api_secret}}"}]),
                    "url": {
                        "raw": "{{base_url}}/api/method/kamra."
                               f"{e['module']}.{e['name']}",
                        "host": ["{{base_url}}"],
                        "path": ["api", "method",
                                 f"kamra.{e['module']}.{e['name']}"],
                    },
                    "description": e["doc"],
                },
            }
            if body:
                req["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(body, indent=2),
                    "options": {"raw": {"language": "json"}},
                }
            folder["item"].append(req)
        items.append(folder)

    collection = {
        "info": {
            "name": "Kamra PMS API",
            "description":
                "The full Kamra REST surface. Set base_url (e.g. "
                "https://pms.yourhotel.com), api_key and api_secret in the "
                "collection variables, then call away. Docs: "
                "https://kamrapms.com/docs/api-reference",
            "schema": "https://schema.getpostman.com/json/collection/"
                      "v2.1.0/collection.json",
        },
        "variable": [
            {"key": "base_url", "value": "https://pms.yourhotel.com"},
            {"key": "api_key", "value": ""},
            {"key": "api_secret", "value": ""},
        ],
        "item": items,
    }
    path = os.path.join(HERE, "public", "kamra.postman_collection.json")
    open(path, "w").write(json.dumps(collection, indent=1))


if __name__ == "__main__":
    modules = collect()
    n = write_markdown(modules)
    write_postman(modules)
    print(f"generated api-reference.md + kamra.postman_collection.json "
          f"({n} endpoints)")
