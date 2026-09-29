"""City seats for inbound partner routing.

Holders are empty until a bid is confirmed and paid. Match aliases stay
in sync with kamra-website/src/data/territories.ts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# slug -> partner email. File wins so a paid seat can start receiving
# leads without a code deploy. Path is empty inside most containers.
_HOLDERS_FILE = Path(os.environ.get(
	"KAMRA_HOLDERS", "/var/lib/kamra-leads/holders.json"
))

# slug -> partner email. Only add after a seat is paid.
TERRITORY_HOLDERS: dict[str, str] = {}


def _holders_from_file() -> dict[str, str]:
	try:
		data = json.loads(_HOLDERS_FILE.read_text(encoding="utf-8"))
	except Exception:
		return {}
	partners = data.get("partners") or {}
	out: dict[str, str] = {}
	for seat, slug in (data.get("territories") or {}).items():
		row = partners.get(slug) or {}
		email = row.get("email")
		if email:
			out[seat] = email
	return out or dict(TERRITORY_HOLDERS)

# Specific seats first. Rest-of-country catch-alls last per country.
TERRITORIES: list[dict] = [
	{"slug": "bali", "country": "indonesia",
	 "aliases": ["bali", "ubud", "canggu", "seminyak", "sanur", "denpasar", "uluwatu", "nusa dua"]},
	{"slug": "jakarta", "country": "indonesia",
	 "aliases": ["jakarta", "jabodetabek", "tangerang", "bekasi"]},
	{"slug": "yogyakarta", "country": "indonesia",
	 "aliases": ["yogyakarta", "jogja", "yogya"]},
	{"slug": "lombok", "country": "indonesia",
	 "aliases": ["lombok", "senggigi", "gili"]},
	{"slug": "indonesia-rest", "country": "indonesia",
	 "aliases": ["bandung", "surabaya", "medan", "makassar", "flores", "labuan bajo"]},
	{"slug": "phuket", "country": "thailand",
	 "aliases": ["phuket", "patong", "kata", "karon", "rawai"]},
	{"slug": "bangkok", "country": "thailand",
	 "aliases": ["bangkok", "sukhumvit", "sathorn"]},
	{"slug": "chiang-mai", "country": "thailand",
	 "aliases": ["chiang mai", "chiangmai"]},
	{"slug": "samui-krabi", "country": "thailand",
	 "aliases": ["koh samui", "samui", "krabi", "ao nang", "koh lanta"]},
	{"slug": "thailand-rest", "country": "thailand",
	 "aliases": ["pattaya", "hua hin", "chiang rai", "koh phangan"]},
	{"slug": "kuala-lumpur", "country": "malaysia",
	 "aliases": ["kuala lumpur", "kl", "petaling jaya", "pj", "selangor"]},
	{"slug": "penang-langkawi", "country": "malaysia",
	 "aliases": ["penang", "george town", "georgetown", "langkawi"]},
	{"slug": "malaysia-rest", "country": "malaysia",
	 "aliases": ["johor", "johor bahru", "kota kinabalu", "kuching", "melaka", "malacca"]},
	{"slug": "ho-chi-minh", "country": "vietnam",
	 "aliases": ["ho chi minh", "saigon", "hcmc", "thu duc"]},
	{"slug": "hanoi", "country": "vietnam",
	 "aliases": ["hanoi", "ha noi"]},
	{"slug": "da-nang", "country": "vietnam",
	 "aliases": ["da nang", "danang", "hoi an", "hoian"]},
	{"slug": "vietnam-rest", "country": "vietnam",
	 "aliases": ["nha trang", "phu quoc", "dalat", "da lat", "hue"]},
	{"slug": "manila", "country": "philippines",
	 "aliases": ["manila", "makati", "quezon city", "bgc", "taguig", "pasay"]},
	{"slug": "cebu-boracay", "country": "philippines",
	 "aliases": ["cebu", "boracay", "mandaue", "lapu-lapu"]},
	{"slug": "philippines-rest", "country": "philippines",
	 "aliases": ["palawan", "el nido", "davao", "bohol", "siargao"]},
	{"slug": "singapore", "country": "singapore",
	 "aliases": ["singapore"]},
	{"slug": "siem-reap", "country": "cambodia",
	 "aliases": ["siem reap", "angkor"]},
	{"slug": "phnom-penh", "country": "cambodia",
	 "aliases": ["phnom penh"]},
	{"slug": "cambodia-rest", "country": "cambodia",
	 "aliases": ["sihanoukville", "kampot", "kep"]},
	{"slug": "goa", "country": "india",
	 "aliases": ["goa", "calangute", "anjuna", "panaji", "panjim", "vagator"]},
	{"slug": "kerala", "country": "india",
	 "aliases": ["kerala", "kochi", "cochin", "alleppey", "alappuzha", "munnar", "kozhikode", "trivandrum", "thiruvananthapuram"]},
	{"slug": "rajasthan", "country": "india",
	 "aliases": ["rajasthan", "jaipur", "udaipur", "jodhpur", "jaisalmer", "pushkar"]},
	{"slug": "india-rest", "country": "india",
	 "aliases": ["delhi", "ncr", "bangalore", "bengaluru", "mumbai", "himachal", "manali", "shimla", "rishikesh"]},
	{"slug": "dubai", "country": "uae",
	 "aliases": ["dubai"]},
	{"slug": "uae-rest", "country": "uae",
	 "aliases": ["abu dhabi", "sharjah", "ras al khaimah", "ajman", "doha", "muscat", "jeddah", "riyadh"]},
]

_COUNTRY_ALIASES = {
	"indonesia": "indonesia",
	"thailand": "thailand",
	"malaysia": "malaysia",
	"vietnam": "vietnam",
	"philippines": "philippines",
	"singapore": "singapore",
	"cambodia": "cambodia",
	"india": "india",
	"uae": "uae",
	"united arab emirates": "uae",
	"gulf": "uae",
}


def _norm(value: str) -> str:
	return (value or "").strip().lower()


def _country_slug(country: str) -> str:
	n = _norm(country)
	return _COUNTRY_ALIASES.get(n, n)


def match_territory(city: str = "", country: str = "") -> dict | None:
	needle = _norm(city)
	country_slug = _country_slug(country)
	pool = [t for t in TERRITORIES if not country_slug or t["country"] == country_slug]
	if not pool:
		pool = TERRITORIES
	if needle:
		for t in pool:
			if t["slug"].endswith("-rest"):
				continue
			for alias in t["aliases"]:
				if alias in needle or needle in alias:
					return t
	if country_slug:
		for t in pool:
			if t["slug"].endswith("-rest") and t["country"] == country_slug:
				return t
	return None


def holder_for(city: str = "", country: str = "") -> tuple[str | None, str | None]:
	"""Return (territory_slug, partner_email) when a paid holder exists."""
	territory = match_territory(city, country)
	if not territory:
		return None, None
	email = _holders_from_file().get(territory["slug"]) or TERRITORY_HOLDERS.get(territory["slug"])
	return territory["slug"], email
