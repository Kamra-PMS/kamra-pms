# Write a country pack
A country pack tells Kamra how one country handles their taxes, the tax rates, documentation of guests, invoices, and payment, which informs how each module behaves. See [Country setup & Saudi e-invoicing (ZATCA)](/country-setup).

Without a pack, Kamra uses a generic pack, that defaults to one flat tax rate, plain labels, and files nothing with the government.

This guide is for contributors who want to write a country pack so that the country is an option with presets.

## Before you start

1. Set up a Kamra development setup. Follow the [Quickstart (development) section in the README.](https://github.com/Kamra-PMS/kamra-pms/blob/develop/README.md#quickstart-development)
2. Fork the repository and create a branch from `develop`, named `feat/<country>-pack`.

## Steps to write a country pack
1. Copy `kamra/localization/thailand.py` to `kamra/localization/<module name>.py`. The module name is a Python name: lowercase, no spaces, for example `uae` for the United Arab Emirates.
2. Replace the docstring. Explain what tax your country charges, at what rate, and what the pack does not cover.
3. Delete anything else that is specific to Thailand.
4. Set the constants
	Put these after the docstring:

	```python
	from decimal import Decimal

	DEFAULT_VAT = Decimal("10")

	DEFAULT_CURRENCY = "<currency unit>"
	DEFAULT_TIMEZONE = "<continent/city>"
	DEFAULT_NATIONALITY = "<nationality>"
	ID_TYPES = ["National ID", "Passport", "Driving License", "Other"]
	PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]
	```
	| Constant | What it sets |
	| --- | --- |
	| `DEFAULT_CURRENCY` | The currency the setup screen fills in |
	| `DEFAULT_TIMEZONE` | The time zone the setup screen fills in. Use a time zone name from the tz database. |
	| `DEFAULT_NATIONALITY` | The nationality the front desk starts with |
	| `ID_TYPES` | The ID documents the desk and self check-in accept |
	| `PAYMENT_MODES` | The ways to pay at the counter, POS and till. Use only **Cash**, **Card**, **UPI** and **Bank Transfer**. Kamra drops any other value, because the till, the ledger and the night audit only know those four. |
5. Write the tax functions
	```python
	def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
		v = room_type_doc.get("tax_percent") if room_type_doc else None
		return Decimal(str(v)) if v else DEFAULT_VAT


	def fnb_tax_rate(property) -> float:
		return float(DEFAULT_VAT)


	def tax_rate_options(property) -> list:
		return [0, 10]
	```

	- `calculate_room_tax` returns the tax percent for a room night. It reads the percent typed on the room type and falls back to your default. When the law changes, the hotel types the new number and the code stays as it is.
	- `fnb_tax_rate` returns the percent for restaurant bills.
	- `tax_rate_options` is the list of rates the tax drop-down offers.

	If guest services such as laundry carry another rate, add `services_tax_rate(property)`. Without it, these services use the `fnb_tax_rate`.
6. Write the invoice labels

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

	- `invoice_context` sets the labels on the printed invoice. `split` says how the tax is named and divided. One national tax is one line.
	- `locale` sets the currency symbol and number format.

	Keep `invoice_context` safe to call on an empty property. The setup screen calls it with no data to read your tax labels, so use `prop_doc.get(...)` with a fallback.
7. Open `kamra/hooks.py` and add your module to `kamra_localization`:

	```python
	kamra_localization = {
		...
		"Saudi Arabia": "kamra.localization.saudi",
		"<country name>": "kamra.localization.<module name>",
	}
	```

	The key is the country name and the value is the path to your module. The key must match the country name on the property exactly. The setup screen builds its Region list from this hook.

	Reload your bench so it reads the new hook.

	::: warning A wrong module path fails silently
	If the path in the hook has a typo, Kamra does not raise an error. It quietly uses the generic pack. If your labels look generic, check the path first.
	:::
8. Test your pack. 
	- [Create a property with the country pack](/go-live)
	- [Quote a stay](/reservations#make-a-booking) 
	- [Post a charge](/billing#post-a-charge)
	- [Print the invoice](/billing#close-the-folio-and-print-the-invoice)

## Add an eval check

A check keeps a later change from breaking your pack unseen. The checks live in `kamra/scripts/eval_harness.py`.

1. Pick a name `t<number>` that is free. Check the highest check in `develop`. Look at the open pull requests as well as `develop`. Two checks with the same name do not raise an error. The second silently replaces the first.
2. Write the check and paste it into `eval_harness.py` above `def execute():`. The file already imports `frappe` and defines `check`. The check creates a property in your country, quotes a stay and asserts the rates, the symbol, the labels and the Region list entry:

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
		assert pack.__name__.endswith("<module name>"), pack.__name__
		# the Region list offers the country; this also fails if
		# invoice_context cannot handle an empty property
		assert "<country name>" in {c["country"] for c in supported_countries()}
		q = quote(pname, rt, "2031-06-01", "2031-06-02", 2, 0)
		assert q["nightly"][0]["gst_rate"] == <room tax rate>, q["nightly"]
		assert pack.fnb_tax_rate(pname) == <F&B tax rate>, pack.fnb_tax_rate(pname)
		loc = pack.locale(frappe.get_doc("Property", pname))
		assert loc["currency_symbol"] == "<currency symbol>", loc
		ctx = pack.invoice_context(frappe.get_doc("Property", pname))
		assert ctx["tax_id_label"] == "<tax ID label>", ctx
	```

3. Add your function name to the list of checks inside `execute()`. The decorator alone does not add it to the run. If you resolve a merge conflict in that list, keep every entry from both sides.

`pack.__name__` is the module path, such as `kamra.localization.uae`, so compare it with your module name, not the country name.

Leave state as you found it. The harness rolls a check back only when it fails, so a passing check's changes stay in place for the checks after it. If your check changes a setting, restore it in a `finally` block.

## Open a pull request

1. Commit with a [Conventional Commit](https://www.conventionalcommits.org/) title, for example `feat: add <country name> localization pack`.
2. Push the branch to your fork and open a pull request against `develop`, not `main`.
3. In the description, say which tax rules the pack covers, which it leaves out, and link the rules you used.

You do not need to edit `CHANGELOG.md` or the version. Maintainers write the release notes.

## Good to know

- Prices, tax and invoice labels come from code. A language model never invents a rate.
- If your pack leaves out an optional function, Kamra uses a plain default. If it leaves out a country-only integration such as a payment gateway or a tax return export, that country does not get the feature. Kamra never borrows another country's.
- You can set `NOTICE_LANGUAGES`, `ADULT_AGE`, `MINOR_IDS` and `REGISTRATION_CARD_REQUIRED`. Add `service_code_for`, `tax_split` and `amount_in_words` if your invoices need them. `india/` shows payment gateways and tax returns. `saudi.py` shows e-invoicing.

## Troubleshooting

**My country is not in the Region list.** Check that the hook entry is saved and that the bench has reloaded. Then check the module path for typos.

**The invoice says "Tax" and the rates are 0, 5, 10, 12, 15 and 20.** That is the generic pack. The country on the property does not match the hook key, or the module path is wrong. Both fail silently.

**The setup screen fails when it lists countries.** Your `invoice_context` probably needs data a blank property does not have. Use `prop_doc.get(...)` with a fallback.

## For developers

The seam is `kamra/localization/__init__.py`. `pack_for(property)` and `pack_for_country(country)` resolve a pack from the `kamra_localization` hook, and `supported_countries()` feeds the Region list through the `kamra.api.localization_countries` endpoint. Quotes are built in `kamra/pricing.py`. See [How Kamra works](/how-it-works) for where packs sit, the [API reference](/api-reference) for the endpoints and [MCP tools](/mcp-tools) for the tools that quote and bill through your pack.