# Write a country pack

A country pack is a small Python module that tells Kamra how one country
taxes rooms and food, which ID documents guests show, how invoices are
labelled, and which payment modes the desk and POS accept. Without a pack,
Kamra falls back to a generic flat rate and plain labels. See
[Country setup & Saudi e-invoicing (ZATCA)](/country-setup).

This page is the contributor checklist for shipping a new pack.

## Prerequisites

1. A local Frappe bench with Kamra installed — use the
   [Quickstart (development)](https://github.com/Kamra-PMS/kamra-pms/blob/develop/README.md#quickstart-development)
   section of the README.
2. A fork of the repo and a branch from `develop` named
   `feat/<country>-pack`.

## Build the pack

1. Copy `kamra/localization/thailand.py` to
   `kamra/localization/<module>.py`. The module name is a Python identifier
   (`uae`, `brazil`, `philippines`).
2. Rewrite the module docstring: name the tax, the usual rate, and anything
   the pack deliberately leaves out.
3. Remove Thailand-specific constants and helpers.
4. Set the module constants after the docstring:

	```python
	from decimal import Decimal

	DEFAULT_VAT = Decimal("10")

	DEFAULT_CURRENCY = "<currency unit>"
	DEFAULT_TIMEZONE = "<continent/city>"
	DEFAULT_NATIONALITY = "<nationality>"
	ID_TYPES = ["National ID", "Passport", "Driving License", "Other"]
	PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]
	```

	| Constant | Effect |
	| --- | --- |
	| `DEFAULT_CURRENCY` | Prefill on the property setup screen |
	| `DEFAULT_TIMEZONE` | Prefill; use an IANA tz database name |
	| `DEFAULT_NATIONALITY` | Starting nationality at the front desk |
	| `ID_TYPES` | Documents accepted at desk and self check-in |
	| `PAYMENT_MODES` | Counter, POS and till modes: **Cash**, **Card**, **Bank Transfer**, plus any `INSTANT_PAYMENT_MODES`. Other values are dropped. |
	| `INSTANT_PAYMENT_MODES` | Optional local wallets (India: `["UPI"]`). Each value must already exist on Folio Payment and Cashier Transaction. |

5. Implement the tax hooks:

	```python
	def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
		v = room_type_doc.get("tax_percent") if room_type_doc else None
		return Decimal(str(v)) if v else DEFAULT_VAT


	def fnb_tax_rate(property) -> float:
		return float(DEFAULT_VAT)


	def tax_rate_options(property) -> list:
		return [0, 10]
	```

	- `calculate_room_tax` — percent for a room night (room-type override, else default).
	- `fnb_tax_rate` — percent for restaurant bills.
	- `tax_rate_options` — values offered in the tax drop-down.
	- Optional `services_tax_rate(property)` for laundry and similar; without it, services reuse `fnb_tax_rate`.

6. Implement invoice wording:

	```python
	def invoice_context(prop_doc) -> dict:
		return {
			"tax_label": "VAT",
			"tax_id_label": "VAT No.",
			"service_code": None,
			"sac": None,
			"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
			"split": [("vat", Decimal("1"))],
			"footer": "This is a computer-generated invoice.",
		}


	def locale(prop_doc) -> dict:
		return {
			"currency_symbol": "EX$",
			"locale": "en-US",
			"currency": prop_doc.get("currency") or "<currency unit>",
			"tax_label": "VAT",
			"tax_id_label": "VAT No.",
			"tax_rates": tax_rate_options(prop_doc.name),
		}
	```

	`invoice_context` must tolerate an empty property — the setup screen
	calls it with no data. Prefer `prop_doc.get(...)` with a fallback.
	`split` names and divides the tax line(s).

7. Register the pack in `kamra/hooks.py` under `kamra_localization`:

	```python
	kamra_localization = {
		...
		"Saudi Arabia": "kamra.localization.saudi",
		"<country name>": "kamra.localization.<module>",
	}
	```

	The key must match the Property country field exactly. Reload the bench
	after editing the hook.

	::: warning Wrong paths fail quietly
	A typo in the module path does not raise. Kamra silently uses the
	generic pack. If labels look generic, check the path first.
	:::

8. Smoke-test on a property that uses the country:
	- [Create the property](/go-live)
	- [Quote a stay](/reservations#make-a-booking)
	- [Post a charge](/billing#post-a-charge)
	- [Print an invoice](/billing#close-the-folio-and-print-the-invoice)

## Eval harness check

Add a regression check in `kamra/scripts/eval_harness.py` so a later change
cannot quietly break the pack.

1. Choose a free `t<number>` name. Look at `develop` and open PRs — a
   duplicate name silently replaces the earlier check.
2. Insert the check above `def execute():`. Assert the pack module, Region
   list entry, quote rate, F&B rate, currency symbol and tax-ID label:

	```python
	@check("<country name> pack: tax rates, labels and Region list entry")
	def t<number>():
		from kamra.localization import pack_for, supported_countries
		from kamra.pricing import quote

		pname = "EVAL <country name> Hotel"
		if not frappe.db.exists("Property", pname):
			frappe.get_doc({
				"doctype": "Property", "property_name": pname,
				"city": "Eval", "country": "<country name>",
			}).insert(ignore_permissions=True)
		rt = frappe.get_doc({
			"doctype": "Room Type", "property": pname,
			"room_type_code": "STD", "room_type_name": "Standard",
			"base_price": 4000, "base_occupancy": 2,
			"adults_capacity": 2, "children_capacity": 1,
		}).insert(ignore_permissions=True).name

		pack = pack_for(pname)
		assert pack.__name__.endswith("<module>"), pack.__name__
		assert "<country name>" in {c["country"] for c in supported_countries()}
		q = quote(pname, rt, "2031-06-01", "2031-06-02", 2, 0)
		assert q["nightly"][0]["gst_rate"] == <room tax rate>, q["nightly"]
		assert pack.fnb_tax_rate(pname) == <F&B tax rate>, pack.fnb_tax_rate(pname)
		loc = pack.locale(frappe.get_doc("Property", pname))
		assert loc["currency_symbol"] == "<currency symbol>", loc
		ctx = pack.invoice_context(frappe.get_doc("Property", pname))
		assert ctx["tax_id_label"] == "<tax ID label>", ctx
	```

3. Append the function name to the list inside `execute()`. The decorator
   alone does not schedule the check. On merge conflicts, keep every entry
   from both sides.

`pack.__name__` is the import path (`kamra.localization.uae`), so compare
against the module name, not the country string.

Restore any Property setting you change in a `finally` block. The harness
only rolls back a check when it fails.

## Pull request

1. Commit with a Conventional Commit title such as
   `feat: add <country name> localization pack`.
2. Open the PR against `develop` (not `main`).
3. Describe which tax rules the pack covers, which it omits, and link the
   official sources you used.

Leave `CHANGELOG.md` and the version alone — maintainers write the release
notes.

## Notes

- Rates and invoice labels always come from code. The language model never
  invents a tax percent.
- Missing optional hooks fall back to plain defaults. Country-only
  integrations (payment gateways, tax returns) are never borrowed from
  another pack.
- Optional constants include `NOTICE_LANGUAGES`, `ADULT_AGE`, `MINOR_IDS`
  and `REGISTRATION_CARD_REQUIRED`. Add `service_code_for`, `tax_split`
  and `amount_in_words` when invoices need them. See `india/` for gateways
  and returns, and `saudi.py` for e-invoicing.

## Troubleshooting

**Country missing from Region.** Confirm the hook entry is saved, the bench
was reloaded, and the module path has no typo.

**Invoice says "Tax" with rates 0, 5, 10, 12, 15, 20.** That is the generic
pack. The Property country does not match the hook key, or the module path
is wrong. Both fail silently.

**Setup screen crashes listing countries.** `invoice_context` probably
requires fields a blank property does not have. Use `prop_doc.get(...)`
with a fallback.

## For developers

The seam is `kamra/localization/__init__.py`. `pack_for(property)` and
`pack_for_country(country)` resolve packs from the `kamra_localization`
hook; `supported_countries()` feeds the Region list through
`kamra.api.localization_countries`. Quotes are built in `kamra/pricing.py`.
See [How Kamra works](/how-it-works), the [API reference](/api-reference)
and [MCP tools](/mcp-tools).
