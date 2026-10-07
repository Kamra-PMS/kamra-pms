"""Redact guest contact / ID fields in Kamra Agent tool results before they
are sent to an external LLM provider (DPDP s.8 / s.16 — issue #88)."""

from __future__ import annotations

_CONTACT_KEY_TOKENS = (
	"phone",
	"mobile",
	"whatsapp",
	"email",
	"aadhaar",
	"passport",
	"id_number",
	"id_no",
	"national_id",
	"gstin",
	"pan",
	"contact_no",
)


def is_contact_field(key: str) -> bool:
	k = (key or "").lower().replace("-", "_")
	return any(t in k for t in _CONTACT_KEY_TOKENS)


def mask_contact_value(value, *, strict: bool):
	if value is None:
		return value
	if strict:
		return "[redacted]"
	s = str(value).strip()
	if not s:
		return value
	digits = "".join(c for c in s if c.isdigit())
	if len(digits) >= 4:
		return f"***{digits[-4:]}"
	if "@" in s:
		local, _, domain = s.partition("@")
		if local and domain:
			return f"{local[0]}***@{domain}"
	return "***"


def scrub_for_llm(data, *, strict: bool):
	"""Recursively mask contact-like fields in tool JSON sent to providers."""
	if isinstance(data, dict):
		out = {}
		for key, val in data.items():
			if is_contact_field(key):
				if isinstance(val, (dict, list)):
					out[key] = scrub_for_llm(val, strict=True if strict else strict)
				else:
					out[key] = mask_contact_value(val, strict=strict)
			else:
				out[key] = scrub_for_llm(val, strict=strict)
		return out
	if isinstance(data, list):
		return [scrub_for_llm(item, strict=strict) for item in data]
	return data


def processor_disclosure(base_url: str | None) -> str:
	"""Plain-language note for Settings — who processes chat/tool payloads."""
	base = (base_url or "").lower()
	if "11434" in base or "ollama" in base or base.startswith("http://127.0.0.1"):
		return (
			"Local (Ollama): when the endpoint runs on this server or your LAN, "
			"chat and tool data stay on your infrastructure — no third-party LLM transfer."
		)
	if "openai.com" in base or "azure.com" in base:
		return (
			"OpenAI / Azure OpenAI: messages and tool results are processed under "
			"your cloud account (typically outside India unless you chose a regional deployment)."
		)
	if "generativelanguage.googleapis.com" in base or "google" in base:
		return (
			"Google Gemini: messages and tool results are processed under your "
			"Google AI / Cloud account (cross-border transfer may apply)."
		)
	if "groq.com" in base:
		return (
			"Groq: messages and tool results are processed under your Groq account "
			"(United States — cross-border transfer may apply)."
		)
	if "openrouter.ai" in base:
		return (
			"OpenRouter: routes to the model you selected; that upstream provider "
			"processes messages and tool results under its terms and region."
		)
	return (
		"Your configured endpoint processes chat messages and tool results under "
		"that provider's terms, privacy policy, and region."
	)
