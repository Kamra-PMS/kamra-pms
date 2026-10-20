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


_BUILTIN: dict[str, type[DoorLockAdapter]] = {ManualAdapter.key: ManualAdapter}


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
