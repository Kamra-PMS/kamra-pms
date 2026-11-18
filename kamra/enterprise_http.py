# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Small JSON HTTP helper for Enterprise adapters.

Stdlib only, so a test can patch urllib.request.urlopen. Timeouts are short
on purpose: check-in and the scheduler must not wait on a vendor.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def request_json(
	url: str,
	payload: dict | None = None,
	headers: dict | None = None,
	method: str = "POST",
	timeout: int = 8,
) -> tuple[int, str]:
	"""Return (status, body). Status 0 means the host did not answer."""
	data = None
	if payload is not None and method != "GET":
		data = json.dumps(payload).encode()
	req = urllib.request.Request(
		url,
		data=data,
		headers={"Content-Type": "application/json", "Accept": "application/json",
		         **(headers or {})},
		method=method,
	)
	try:
		with urllib.request.urlopen(req, timeout=timeout) as res:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- URL is the property's configured provider endpoint, not a redirect the caller follows
			return int(res.status), res.read().decode()[:4000]
	except urllib.error.HTTPError as exc:
		try:
			body = exc.read().decode()[:4000]
		except Exception:
			body = str(exc)
		return int(exc.code or 0), body
	except Exception as exc:
		return 0, str(exc)[:500]
