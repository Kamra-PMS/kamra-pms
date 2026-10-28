"""Brazil localization pack.

Brazilian hotel accommodation is subject to municipal service tax (ISS -
Imposto Sobre Serviços), which typically ranges from 2% to 5% depending on
the municipality. Standard statutory default is 5%:

  - the room tax rate comes from the Room Type's tax percent (default 5%),
    allowing operators to adjust for their local municipality (e.g. 2% to 5%)
  - hotel F&B and restaurant supplies default to 5%
  - default timezone is America/Sao_Paulo (Horário de Brasília, GMT-3).
    Properties located across Brazil's other timezones (America/Noronha GMT-2,
    America/Fortaleza, America/Belem, America/Manaus GMT-4, America/Cuiaba,
    America/Rio_Branco GMT-5) can configure their local zone in Property Settings.
  - tax invoices identify businesses and individuals via CNPJ or CPF and
    serve as NFS-e (Nota Fiscal de Serviços Eletrônica) reference documents
  - front desk accepts standard Brazilian identification documents: CPF,
    RG, Passport, and CNH (Carteira Nacional de Habilitação)
"""

from decimal import Decimal

import frappe

DEFAULT_ISS = Decimal("5")

DEFAULT_CURRENCY = "BRL"
DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_NATIONALITY = "Brazilian"
ID_TYPES = ["CPF", "RG", "Passport", "Driving License (CNH)", "Other"]
PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Municipal ISS on hotel accommodation - standard default 5%, or as
	configured on the Room Type."""
	v = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(v)) if v else DEFAULT_ISS


def fnb_tax_rate(property) -> float:
	"""Hotel restaurant tax rate."""
	rates = frappe.get_all(
		"Room Type", filters={"property": property, "disabled": 0},
		pluck="tax_percent", limit=5)
	first = next((r for r in rates if r), None)
	return float(first) if first else float(DEFAULT_ISS)


def tax_rate_options(property) -> list:
	return [0, 2, 3, 4, 5, 10]


def invoice_context(prop_doc) -> dict:
	return {
		"tax_label": "ISS",
		"tax_id_label": "CNPJ / CPF",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		"split": [("iss", Decimal("1"))],
		"footer": "NFS-e - Documento Auxiliar de Nota Fiscal de Serviços. "
		          "This is a computer-generated invoice.",
	}


def locale(prop_doc) -> dict:
	return {
		"currency_symbol": "R$",
		"locale": "pt-BR",
		"currency": prop_doc.get("currency") or "BRL",
		"tax_label": "ISS",
		"tax_id_label": "CNPJ / CPF",
		"tax_rates": tax_rate_options(prop_doc.name if hasattr(prop_doc, "name") else None),
	}
