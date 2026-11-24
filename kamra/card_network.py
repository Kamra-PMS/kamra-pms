"""Which card network a card payment came from (Visa, RuPay, ...).

The desk picks the card type from the card machine slip and may add the last
four digits. Only these two values are kept, never a full card number. This
module holds the list of networks and the one check every payment path uses.
"""

import re

import frappe
from frappe import _

NETWORKS = [
	"Visa", "Mastercard", "RuPay", "American Express", "Diners Club", "Discover",
	"JCB", "UnionPay", "Maestro", "Mir", "Elo", "Other",
]


def clean(mode, network, last4):
	"""Return (network, last4) to store for a payment taken in `mode`.

	Anything but the Card mode returns (None, None). A card payment from a
	caller that sends no network is still accepted, so existing integrations
	keep working; the screens ask for the network themselves.
	"""
	network = (network or "").strip()
	last4 = (last4 or "").strip()
	if (mode or "") != "Card" or not network:
		return None, None
	if network not in NETWORKS:
		frappe.throw(_("Card network must be one of: {0}.").format(", ".join(NETWORKS)))
	if last4 and not re.fullmatch(r"\d{4}", last4):
		frappe.throw(_("Give exactly the last 4 digits of the card, or leave it empty."))
	return network, last4 or None
