"""Channel-manager seam - provider-agnostic OTA connectivity.

Kamra never talks to an OTA directly; a channel manager does (Channex,
STAAH, AioSell, ...). Every provider adapter is one module implementing
two functions:

    push_ari(conn, snapshot) -> (ok: bool, detail: str)
        Deliver availability + rates to the provider. `snapshot` is
        Kamra's normalized shape (see channel_manager.ari_snapshot):
        [{room_type, external_room_id, external_rate_id, days: [
            {date, available, rate}]}]

    parse_webhook(conn, payload) -> list[dict]
        Turn the provider's booking webhook into normalized events:
        [{event: "book"|"modify"|"cancel", ota_ref, channel,
          room_type_external_id, check_in, check_out, adults, children,
          guest_name, phone, email, total, currency, notes}]

Adapters hold ONLY protocol translation. Booking creation, validation,
availability math and pricing stay in kamra.channel_manager - an OTA
booking obeys exactly the rules a front-desk booking does.

Like the localization packs, the registry is a plain dict so a future
external app can claim a provider via the kamra_channel_providers hook.
"""

import importlib

import frappe

_BUILTIN = {
	"Channex": "kamra.channels.channex",
	"STAAH": "kamra.channels.staah",
	"AioSell": "kamra.channels.aiosell",
}


def provider_for(name: str):
	mapping = dict(_BUILTIN)
	for hooked in frappe.get_hooks("kamra_channel_providers") or []:
		if isinstance(hooked, dict):
			mapping.update(hooked)
	target = mapping.get(name)
	if not target:
		frappe.throw(f"No channel-manager provider registered for {name}.")
	return importlib.import_module(target)
