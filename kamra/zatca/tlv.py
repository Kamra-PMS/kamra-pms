"""ZATCA Phase 1 QR payload: tag-length-value, base64.

Tags (E-invoicing Resolution, Phase 1 "generation"):
  1 seller name   2 seller VAT number   3 invoice timestamp
  4 invoice total (with VAT)   5 VAT total

Phase 2 adds 6 (invoice hash), 7 (ECDSA signature), 8 (public key) and,
for simplified invoices, 9 (the CSID's certificate signature) - those only
exist once the EGS unit is onboarded and signing, so they are appended by
the signer, not here.
"""

import base64


def _tlv(tag: int, value: str) -> bytes:
	raw = value.encode("utf-8")
	if len(raw) > 255:
		# one-byte length: ZATCA's QR fields are all short; a seller name
		# this long is a data-entry mistake, not something to encode
		raw = raw[:255]
	return bytes([tag, len(raw)]) + raw


def phase1_qr(seller_name: str, vat_number: str, timestamp: str,
              total_with_vat: str, vat_total: str) -> str:
	payload = b"".join([
		_tlv(1, seller_name),
		_tlv(2, vat_number),
		_tlv(3, timestamp),
		_tlv(4, total_with_vat),
		_tlv(5, vat_total),
	])
	return base64.b64encode(payload).decode("ascii")


def decode(qr_b64: str) -> dict[int, str]:
	"""For tests and support: read a QR payload back into its tags."""
	raw = base64.b64decode(qr_b64)
	out, i = {}, 0
	while i < len(raw):
		tag, length = raw[i], raw[i + 1]
		out[tag] = raw[i + 2:i + 2 + length].decode("utf-8")
		i += 2 + length
	return out
