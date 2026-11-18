"""Door lock interface - the contract a lock vendor connector implements.

Kamra ships no vendor connector yet. This module fixes the seam so one can
be added (in this app or a separate Frappe app) without touching the front
desk: a connector subclasses DoorLockAdapter, registers itself, and the
property picks it in Settings -> Front Desk -> Door locks.

    class AcmeAdapter(DoorLockAdapter):
        key = "acme"
        label = "Acme Locks (cloud)"

        def issue_key(self, request: KeyRequest) -> KeyResult: ...
        def revoke_keys(self, property, reservation, room) -> KeyResult: ...

    # in your app's hooks.py
    kamra_door_lock_adapters = {"acme": "acme_kamra.locks.AcmeAdapter"}

Rules for a connector:
    - it is called after Kamra has decided (check-in done, room assigned);
      it never decides who gets a key, and it never changes the booking;
    - it gets the room, the stay window and a key count - no guest contact
      details or ID documents;
    - credentials live in the connector's own encrypted settings, never in
      the payload or the logs;
    - a failure returns KeyResult(ok=False, message=...) for the desk to
      show; it must not raise into check-in.

A connector can also listen to the guest.checked_in / guest.checked_out
outbound webhooks instead of running in-process (middleware on the lock
vendor's side) - see docs-site/integrations.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import frappe

DEFAULT_ADAPTER = "manual"


@dataclass(frozen=True)
class KeyRequest:
	property: str
	reservation: str
	room: str
	room_number: str
	valid_from: str  # ISO datetime, property local time
	valid_to: str
	key_count: int = 1
	guest_name: str | None = None  # for the card label only
	options: dict = field(default_factory=dict)  # vendor-specific (encoder id, ...)


@dataclass
class KeyResult:
	ok: bool
	adapter: str
	message: str = ""
	key_ids: list = field(default_factory=list)  # vendor card / credential ids
	manual: bool = False  # staff must finish it at the vendor's encoder


class DoorLockAdapter(ABC):
	"""Base class every lock connector implements."""

	key: str = ""
	label: str = ""
	# what the connector can do, so the desk only offers those buttons
	supports_mobile_keys: bool = False
	supports_revoke: bool = True

	@abstractmethod
	def issue_key(self, request: KeyRequest) -> KeyResult:
		"""Make `request.key_count` keys for the room, valid for the stay."""

	@abstractmethod
	def revoke_keys(self, property: str, reservation: str, room: str) -> KeyResult:
		"""Cancel every key issued for this stay and room (check-out, room
		move, lost card)."""

	def health(self, property: str) -> dict:
		"""Optional: is the vendor reachable / configured for this property?"""
		return {"ok": True}


class ManualAdapter(DoorLockAdapter):
	"""No connected lock system: staff cut cards at the vendor's encoder.
	Returns an instruction so the desk can prompt them; does nothing else."""

	key = "manual"
	label = "Manual (encode cards at the lock's encoder)"
	supports_revoke = False

	def issue_key(self, request: KeyRequest) -> KeyResult:
		return KeyResult(
			ok=True, adapter=self.key, manual=True,
			message=f"Encode {request.key_count} key card(s) for room "
			        f"{request.room_number}, valid until {request.valid_to}.")

	def revoke_keys(self, property: str, reservation: str, room: str) -> KeyResult:
		return KeyResult(ok=True, adapter=self.key, manual=True,
		                 message="Collect the key cards; they expire at check-out time.")


class HttpEncoderAdapter(DoorLockAdapter):
	"""POST key requests to a URL the property configures.

	Enterprise only. The encoder (or a proxy in front of the lock vendor)
	accepts JSON: action, property, reservation, room, room_number,
	valid_from, valid_to, key_count, guest_name. It returns 2xx and may
	include key_ids. The shared secret is an Enterprise Secret, sent as
	Authorization: Bearer <secret> when one is set. A failure is a result,
	never an exception, so check-in still completes.
	"""

	key = "http"
	label = "HTTP encoder (Enterprise)"

	def issue_key(self, request: KeyRequest) -> KeyResult:
		return self._call("issue", request)

	def revoke_keys(self, property: str, reservation: str, room: str) -> KeyResult:
		request = KeyRequest(
			property=property, reservation=reservation, room=room,
			room_number=room, valid_from="", valid_to="", key_count=0)
		return self._call("revoke", request)

	def _call(self, action: str, request: KeyRequest) -> KeyResult:
		from kamra.edition import is_enterprise
		from kamra.enterprise_http import request_json
		from kamra.enterprise_logic import parse_provider_json
		from kamra.settings import get_setting
		if not is_enterprise(request.property):
			return KeyResult(
				ok=False, adapter=self.key,
				message="HTTP key encoding is a Kamra Enterprise feature. "
				        "Enable Enterprise for this property, or use manual encoding.")
		url = (get_setting(request.property, "ent_door_url", "") or "").strip()
		if not url:
			return KeyResult(
				ok=False, adapter=self.key,
				message="Set the encoder URL under Settings, Enterprise.")
		secret = ""
		if frappe.db.exists("DocType", "Enterprise Secret") and frappe.db.exists(
			"Enterprise Secret", request.property):
			secret = frappe.get_doc("Enterprise Secret", request.property).get_password(
				"door_http_secret", raise_exception=False) or ""
		headers = {"Authorization": f"Bearer {secret}"} if secret else {}
		status, body = request_json(url, {
			"action": action,
			"property": request.property,
			"reservation": request.reservation,
			"room": request.room,
			"room_number": request.room_number,
			"valid_from": request.valid_from,
			"valid_to": request.valid_to,
			"key_count": request.key_count,
			"guest_name": request.guest_name,
		}, headers=headers)
		parsed = parse_provider_json(
			status, body,
			ok_message="Key encoded." if action == "issue" else "Keys cancelled.")
		return KeyResult(
			ok=parsed["ok"], adapter=self.key, message=parsed["message"],
			key_ids=parsed["ids"], manual=False)


_BUILTIN: dict[str, type[DoorLockAdapter]] = {
	ManualAdapter.key: ManualAdapter,
	HttpEncoderAdapter.key: HttpEncoderAdapter,
}


def registered_adapters() -> dict[str, type[DoorLockAdapter]]:
	"""Built-in adapters plus every app's `kamra_door_lock_adapters` hook."""
	out = dict(_BUILTIN)
	hooks = frappe.get_hooks("kamra_door_lock_adapters") or {}
	# dict hooks merge across apps as {key: [path, ...]}; the last app wins
	for key, paths in (hooks.items() if isinstance(hooks, dict) else []):
		path = paths[-1] if isinstance(paths, (list, tuple)) else paths
		try:
			cls = frappe.get_attr(path)
		except Exception:
			frappe.log_error(title=f"Door lock adapter {key} failed to load")
			continue
		if isinstance(cls, type) and issubclass(cls, DoorLockAdapter):
			out[key] = cls
	return out


def get_adapter(property: str | None) -> DoorLockAdapter:
	"""The adapter the property chose; the manual one when unset or unknown."""
	from kamra.settings import get_setting
	key = get_setting(property, "door_lock_adapter", DEFAULT_ADAPTER) or DEFAULT_ADAPTER
	cls = registered_adapters().get(key) or ManualAdapter
	return cls()
