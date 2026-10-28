"""Guest-facing booking engine API - the only allow_guest surface.

Read: property showcase + live availability with real quotes.
Write: one endpoint, create a Website booking. Everything else stays
behind auth. Money still comes only from the pricing engine.
"""

import re

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, date_diff

from kamra.authz import act_as
from kamra.booking_slugs import resolve_public_slug, slugify
from kamra.install import AGENT_EMAIL


def _room_type_filters(property: str, listing_slug: str | None = None,
                       location_slug: str | None = None) -> dict:
	filters: dict = {"property": property, "disabled": 0}
	if listing_slug:
		filters["listing_slug"] = listing_slug
	if location_slug:
		filters["location_slug"] = location_slug
	return filters


def _room_type_payload(rt) -> dict:
	return {
		"name": rt.name,
		"room_type_name": rt.room_type_name,
		"listing_slug": rt.get("listing_slug"),
		"location_slug": rt.get("location_slug"),
		"description": rt.description,
		"base_price": float(rt.base_price),
		"base_occupancy": rt.base_occupancy,
		"adults_capacity": rt.adults_capacity,
		"children_capacity": rt.children_capacity,
		"bed_type": rt.bed_type,
		"room_view": rt.room_view,
		"room_category": rt.get("room_category"),
		"amenities": [a.strip() for a in re.split(r"[,\n]", rt.amenities or "") if a.strip()],
		"media": [
			{"media_type": m.media_type, "url": m.url, "caption": m.caption}
			for m in (rt.get("media") or [])
		],
		"location_name": rt.get("location_name"),
		"location_address": rt.get("location_address"),
		"google_maps_url": rt.get("google_maps_url"),
		"latitude": rt.get("latitude"),
		"longitude": rt.get("longitude"),
	}


def _property_payload(prop) -> dict:
	return {
		"name": prop.name,
		"property_name": prop.property_name,
		"property_slug": prop.get("page_slug") or slugify(prop.property_name),
		"description": prop.get("showcase_description"),
		"logo_url": prop.get("logo_url"),
		"hero_image": prop.get("hero_image"),
		"brand_accent": prop.get("brand_accent") or "Emerald",
		"star_category": prop.get("star_category"),
		"address_line": prop.address_line,
		"city": prop.city, "state": prop.state,
		"pincode": prop.pincode,
		"country": prop.get("country") or "India",
		"phone": prop.phone, "email": prop.email,
		"website": prop.website,
		"google_reviews_url": prop.get("google_reviews_url"),
		"tripadvisor_url": prop.get("tripadvisor_url"),
		"amenities": [a.strip() for a in re.split(r"[,\n]", prop.get("property_amenities") or "") if a.strip()],
		"checkin_time": str(prop.checkin_time or ""),
		"checkout_time": str(prop.checkout_time or ""),
		"privacy_contact": prop.get("privacy_contact") or prop.email or prop.phone,
		"guest_retention_months": prop.get("guest_retention_months") or 0,
		"driving_directions": prop.get("driving_directions"),
		"latitude": prop.get("latitude"),
		"longitude": prop.get("longitude"),
		"gallery": [
			{"url": m.url, "caption": m.caption}
			for m in (prop.get("gallery") or [])
		],
		"faqs": [
			{"question": f.question, "answer": f.answer}
			for f in (prop.get("faqs") or [])
		],
		"house_rules": prop.get("house_rules"),
		"pets_policy": prop.get("pets_policy"),
		"children_policy": prop.get("children_policy"),
		"extra_bed_policy": prop.get("extra_bed_policy"),
		"meta_title": prop.get("meta_title"),
		"meta_description": prop.get("meta_description"),
		"og_image": prop.get("og_image"),
		"page_slug": prop.get("page_slug"),
		"booking_engine_enabled": prop.get("booking_engine_enabled"),
		"payment_mode": prop.get("booking_payment_mode") or "Pay at hotel",
		"advance_percent": float(prop.get("advance_percent") or 0),
		"registration_fee": float(prop.get("registration_fee") or 0),
		"cleaning_fee": float(prop.get("cleaning_fee") or 0),
		"pets_allowed": int(prop.get("pets_allowed") or 0),
		"pet_charge": float(prop.get("pet_charge") or 0),
		"pet_charge_basis": prop.get("pet_charge_basis") or "Per stay",
		"security_deposit_amount": float(prop.get("security_deposit_amount") or 0),
		"minimum_nights": int(prop.get("minimum_nights") or 1),
		"free_cancel_days": int(prop.get("free_cancel_days") or 0),
		"cancellation_fee": prop.get("cancellation_fee") or "None",
		"booking_mode": prop.get("booking_mode") or "Instant",
		"property_kind": prop.get("property_kind") or "Hotel",
	}


def _build_locations(prop, room_types: list[dict]) -> list[dict]:
	"""Group room types into shareable site/property cards for the catalog."""
	locations = []
	seen = {}
	for rt in room_types:
		key = rt["location_slug"] or rt["location_name"] or "__property__"
		if key not in seen:
			cover = None
			for m in rt.get("media") or []:
				if m.get("url"):
					cover = m["url"]
					break
			seen[key] = {
				"name": rt["location_name"] or prop.property_name,
				"slug": rt["location_slug"] or None,
				"address": rt["location_address"] or prop.address_line,
				"google_maps_url": rt["google_maps_url"],
				"latitude": rt["latitude"] if rt["location_name"] else prop.get("latitude"),
				"longitude": rt["longitude"] if rt["location_name"] else prop.get("longitude"),
				"phone": prop.get("phone"),
				"cover_image": cover or prop.get("hero_image"),
				"city": prop.city,
				"state": prop.state,
				"room_types": [],
				"listing_count": 0,
				"from_rate": rt["base_price"],
			}
			locations.append(seen[key])
		seen[key]["room_types"].append(rt["name"])
		seen[key]["listing_count"] = len(seen[key]["room_types"])
		seen[key]["from_rate"] = min(seen[key]["from_rate"], rt["base_price"])
		if not seen[key].get("cover_image"):
			for m in rt.get("media") or []:
				if m.get("url"):
					seen[key]["cover_image"] = m["url"]
					break
		# Prefer a maps pin from any listing that has one.
		if not seen[key].get("google_maps_url") and rt.get("google_maps_url"):
			seen[key]["google_maps_url"] = rt["google_maps_url"]
		if seen[key].get("latitude") is None and rt.get("latitude") is not None:
			seen[key]["latitude"] = rt["latitude"]
			seen[key]["longitude"] = rt["longitude"]
	return locations


@frappe.whitelist(allow_guest=True)
def catalog_index(property_slug: str | None = None):
	"""Entry point for /book — how many properties, sites, or listings to show.

	Several properties live: mode "properties" lists them, and the guest
	picks one - /book?property=<slug> (or /stay/<slug>) calls back with
	that property's slug and gets its own sites / listings / catalog."""
	from kamra.booking_slugs import property_for_slug

	if property_slug:
		chosen = property_for_slug(property_slug)
		if not chosen:
			frappe.throw("Property not found.", frappe.DoesNotExistError)
		properties = [frappe._dict(name=chosen)]
	else:
		properties = frappe.get_all(
			"Property",
			filters={"booking_engine_enabled": 1, "disabled": 0},
			fields=["name", "property_name", "page_slug", "city", "state",
			        "hero_image", "logo_url", "property_kind",
			        "showcase_description"],
			order_by="property_name asc",
		)
	if len(properties) > 1:
		for p in properties:
			p["property_slug"] = p.get("page_slug") or slugify(p["property_name"])
			p["description"] = p.pop("showcase_description", None)
			# a card needs a "from" price and a photo even when the
			# property never set a hero image
			p["from_rate"] = float(frappe.db.sql(
				"""SELECT MIN(base_price) FROM `tabRoom Type`
				WHERE property = %s AND disabled = 0""", p.name)[0][0] or 0)
			if not p.get("hero_image"):
				cover = frappe.db.sql(
					"""SELECT m.url FROM `tabRoom Type Media` m
					JOIN `tabRoom Type` rt ON rt.name = m.parent
					WHERE m.parenttype = 'Room Type' AND rt.property = %s
					  AND rt.disabled = 0 AND IFNULL(m.url, '') != ''
					ORDER BY rt.base_price, m.idx LIMIT 1""", p.name)
				p["hero_image"] = cover[0][0] if cover else None
		return {"mode": "properties", "properties": properties,
		        "ui_locale": _public_locale(properties[0].name)}

	property_name = properties[0].name if properties else default_property()
	prop = frappe.get_doc("Property", property_name)
	room_types = []
	for rt_name in frappe.get_all(
		"Room Type", filters={"property": property_name, "disabled": 0},
		pluck="name", order_by="base_price asc",
	):
		room_types.append(_room_type_payload(frappe.get_doc("Room Type", rt_name)))
	locations = _build_locations(prop, room_types)
	sites = [loc for loc in locations if loc.get("slug")]

	if len(sites) > 1:
		return {
			"mode": "sites",
			"property": property_name,
			"sites": sites,
			"ui_locale": _public_locale(property_name),
		}
	if len(room_types) == 1 and room_types[0].get("listing_slug"):
		return {
			"mode": "single_listing",
			"property": property_name,
			"listing_slug": room_types[0]["listing_slug"],
		}
	return {
		"mode": "catalog",
		"property": property_name,
		"listing_count": len(room_types),
		"ui_locale": _public_locale(property_name),
	}


@frappe.whitelist(allow_guest=True)
def resolve_slug(slug: str):
	"""Resolve /stay/:slug to a listing or multi-listing site."""
	return resolve_public_slug(slug)


@frappe.whitelist(allow_guest=True)
def site_info():
	"""Public site metadata for the login/boot screen.

	demo_mode is true only on the seeded demo site (seed_demo sets the
	`kamra_demo_mode` default), so a real install never advertises the
	demo login accounts. The running version is public on purpose: it is
	what a bug report and the login screen quote.
	"""
	from kamra import __version__
	return {
		"demo_mode": frappe.db.get_default("kamra_demo_mode") == "1",
		"app": "kamra",
		"version": __version__,
		# `bench --site <site> set-config kamra_channel nightly` labels a
		# channel build so it isn't mistaken for the last stable release;
		# kamra_build (a short commit id) is optional.
		"channel": (frappe.conf.get("kamra_channel") or "")[:20] or None,
		"build": (frappe.conf.get("kamra_build") or "")[:12] or None,
	}


@frappe.whitelist(allow_guest=True)
def default_property():
	"""Which Property the public booking engine (``/book``) should show.

	Each Kamra deploy is single-tenant: one site = one hotel/villa. The
	frontend used to hardcode the demo property name, which only worked
	on the seeded demo site and broke the booking engine on every other
	tenant (``Property <name> not found`` / permission error for Guest).

	Picks the Property with booking_engine_enabled=1; if none are flagged
	(fresh install) or several are, falls back to the first Property so
	the page still renders instead of hanging on a guest permission error.
	"""
	enabled = frappe.get_all(
		"Property", filters={"booking_engine_enabled": 1}, pluck="name", limit=1,
	)
	if enabled:
		return enabled[0]
	any_property = frappe.get_all("Property", pluck="name", limit=1)
	if any_property:
		return any_property[0]
	frappe.throw("No property configured for this site.")
	raise  # frappe.throw always raises; CodeQL does not treat it as noreturn


def _public_locale(property: str) -> dict:
	from kamra.localization import pack_for, privacy_terms
	prop = frappe.get_cached_doc("Property", property)
	pack = pack_for(property)
	loc = pack.locale(prop)
	# "" is a valid symbol (generic pack shows bare numbers) - only the
	# missing key falls back to the rupee
	return {"currency_symbol": loc.get("currency_symbol", "₹"),
	        "locale": loc.get("locale") or "en-IN",
	        **privacy_terms(pack)}


@frappe.whitelist(allow_guest=True)
def showcase(property: str, listing_slug: str | None = None,
             location_slug: str | None = None):
	"""Everything the public booking page needs to render."""
	prop = frappe.get_doc("Property", property)
	if not prop.get("booking_engine_enabled"):
		frappe.throw("Online booking is not enabled for this property.")

	room_types = []
	for rt_name in frappe.get_all(
		"Room Type",
		filters=_room_type_filters(property, listing_slug, location_slug),
		pluck="name", order_by="base_price asc",
	):
		room_types.append(_room_type_payload(frappe.get_doc("Room Type", rt_name)))

	locations = _build_locations(prop, room_types)

	experiences = frappe.get_all(
		"Experience",
		filters={"property": property, "disabled": 0,
		         "show_on_booking_page": 1},
		fields=["name", "experience_name", "category", "price", "duration",
		        "description", "image_url", "gst_rate"],
		order_by="category asc",
	)

	meal_plans = frappe.get_all(
		"Meal Plan", filters={"property": property, "disabled": 0},
		fields=["name", "code", "label", "price_per_adult"],
		order_by="price_per_adult asc",
	)

	return {
		"ui_locale": _public_locale(property),
		"property": _property_payload(prop),
		"room_types": room_types,
		"locations": locations,
		"meal_plans": meal_plans,
		"experiences": experiences,
		"scope": {
			"listing_slug": listing_slug,
			"location_slug": location_slug,
		},
	}


@frappe.whitelist(allow_guest=True)
def search_stay(property: str, check_in_date: str, check_out_date: str,
                adults: int = 2, children: int = 0,
                listing_slug: str | None = None,
                location_slug: str | None = None, pets: int = 0,
                child_ages=None):
	"""Availability + real quoted price per room type for the stay.

	`child_ages` (e.g. [3, 8, 13]) lets each room type's age bands decide who
	is free, a child or an adult; without it `children` are all children.
	Each row says whether the room type can take the party: `available`, a
	`reason` when it cannot, and `needs_confirmation` when the party is above
	what it sleeps but within the extra guests it allows by arrangement."""
	# available_rooms is staff-only (@require_roles) since it's also an
	# MCP / Kamra Agent tool; guests need the same availability math without
	# role gate, so this calls the same underlying helpers directly.
	from kamra.api import _available_rooms_raw, _block_hold
	from kamra.pricing import capacity_overflow, quote
	from kamra.siu.availability import has_active_sius, sellable_count

	nights = date_diff(check_out_date, check_in_date)
	if nights < 1:
		frappe.throw("Check-out must be after check-in.")
	if nights > 30:
		frappe.throw("Stays longer than 30 nights: please contact the hotel.")
	ages = _child_ages(child_ages)
	_party(None, adults, children, None)  # at least one adult, before any work

	prop = frappe.get_cached_doc("Property", property)
	results = []
	for rt in frappe.get_all(
		"Room Type",
		filters=_room_type_filters(property, listing_slug, location_slug),
		pluck="name", order_by="base_price asc",
	):
		hold = _block_hold(property, rt, check_in_date, check_out_date)
		if has_active_sius(property, rt):
			left = max(0, sellable_count(
				property, rt, check_in_date, check_out_date) - (hold or 0))
		else:
			free = _available_rooms_raw(
				property, rt, check_in_date, check_out_date)
			if hold:
				free = free[:max(0, len(free) - hold)]
			left = len(free)
		rtd = frappe.get_cached_doc("Room Type", rt)
		a, c, infants = _party(rtd, adults, children, ages)
		above, beds = capacity_overflow(rtd, a, c)
		row = {"room_type": rt, "rooms_left": left, "quote": None,
		       "available": bool(left), "adults": a, "children": c,
		       "infants": infants}
		if above > beds:
			row.update(available=False, reason=TOO_MANY_GUESTS)
			results.append(row)
			continue
		if above:
			row.update(needs_confirmation=True,
			           confirmation_reason=_over_capacity_note(above))
		if left:
			try:
				q = quote(property, rt, check_in_date, check_out_date,
				          a, c, pets=int(pets or 0))
				rules = q.get("stay_rules") or {}
				q.update(_payment_split(prop, q.get("amount_after_tax"),
				                        rules.get("full_payment")))
				row["quote"] = q
				need = max(int(rules.get("minimum_nights") or 0),
				           int(prop.get("minimum_nights") or 1))
				if nights < need:
					row.update(available=False, reason=(
						f"These dates need a stay of at least {need} nights"
						+ (f" ({rules['season']})." if rules.get("season") else ".")))
			except Exception:
				pass  # still list the room type even if this date range cannot be quoted
		results.append(row)
	return results


def _res_by_token(token: str):
	if not token or len(token) < 20:
		frappe.throw("Invalid link.")
	name = frappe.db.get_value("Reservation", {"precheckin_token": token})
	if not name:
		frappe.throw("This check-in link is not valid anymore.")
	return frappe.get_doc("Reservation", name)


@frappe.whitelist(allow_guest=True)
def precheckin_info(token: str):
	"""Stay summary for the pre-arrival check-in page."""
	res = _res_by_token(token)
	if res.status not in ("Confirmed", "Checked In"):
		frappe.throw("This booking is no longer active.")
	prop = frappe.get_doc("Property", res.property)
	guest = frappe.get_doc("Guest", res.guest)
	from kamra.localization import front_desk_vocabulary, pack_for
	vocab = front_desk_vocabulary(pack_for(res.property))
	return {
		"ui_locale": _public_locale(res.property),
		# which IDs this country accepts, and the likely nationality
		"id_types": vocab["id_types"],
		"default_nationality": vocab["default_nationality"],
		"property": {
			"property_name": prop.property_name,
			"logo_url": prop.get("logo_url"),
			"city": prop.city,
			"checkin_time": str(prop.checkin_time or ""),
			"phone": prop.phone,
			"house_rules": prop.get("house_rules"),
			"pets_policy": prop.get("pets_policy"),
			"children_policy": prop.get("children_policy"),
			"extra_bed_policy": prop.get("extra_bed_policy"),
			# drives what the guest is promised about their ID photo; the
			# page must not claim "deleted at checkout" under Store mode
			"id_retention": prop.get("id_retention") or "Store",
			"privacy_contact": prop.get("privacy_contact") or prop.get("email") or prop.phone,
			"guest_retention_months": prop.get("guest_retention_months") or 0,
		},
		"stay": {
			"reservation": res.name,
			"room_type": res.room_type.split("-")[-1],
			"check_in_date": str(res.check_in_date),
			"check_out_date": str(res.check_out_date),
			"nights": res.nights,
			"adults": res.adults,
			"children": res.children,
			"status": res.precheckin_status,
		},
		"guest": {
			"full_name": guest.full_name,
			"phone": guest.phone,
			"email": guest.email,
			"id_type": guest.id_type,
			"has_id_file": bool(guest.get("id_file")),
			"has_address_file": bool(guest.get("address_proof_file")),
			"nationality": guest.nationality,
			# a boolean, never a URL: Frappe refuses a Guest session any
			# private file, so the guest cannot see their own scan back and a
			# read-back endpoint would only be a brute-force oracle for the
			# token. "We have it" is all the page needs to say.
			"has_id_document": bool(res.get("id_document")),
			"id_document_on": str(res.get("id_document_on") or ""),
		},
	}


def _save_id_image(guest: str, data_url: str,
                   field: str = "id_file") -> str | None:
	"""Store a guest document (ID or address proof) as a PRIVATE file
	attached to their profile (upload or camera capture). Replaces any
	earlier copy in the same slot; deleted at checkout under
	Verify & Discard."""
	import base64
	import re as _re
	m = _re.match(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$",
	              data_url or "", _re.S)
	if not m:
		frappe.throw("The ID photo must be a JPEG, PNG or WebP image.")
	if len(m.group(2)) > 8_000_000:  # ~6 MB decoded
		frappe.throw("The ID photo is too large - please retake it.")
	content = base64.b64decode(m.group(2))
	# replace, never accumulate: one current ID document per guest
	for f in frappe.get_all("File", filters={
			"attached_to_doctype": "Guest", "attached_to_name": guest,
			"attached_to_field": field}, pluck="name"):
		frappe.delete_doc("File", f, force=True, ignore_permissions=True)
	ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
	fdoc = frappe.get_doc({
		"doctype": "File",
		"file_name": f"{'address' if field == 'address_proof_file' else 'id'}-{guest}.{ext}",
		"attached_to_doctype": "Guest",
		"attached_to_name": guest,
		"attached_to_field": field,
		"is_private": 1,
		"content": content,
	}).insert(ignore_permissions=True)
	return fdoc.file_url


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=3600)
def precheckin_submit(token: str, id_type: str, id_number: str,
                      email: str = "", nationality: str = "",
                      address_line: str = "", city: str = "",
                      eta: str = "", special_requests: str = "",
                      signature: str = "", consent: int = 0,
                      id_image: str = "", address_image: str = ""):
	"""Guest completes pre-arrival check-in and signs the registration card
	(PRD FR-20 - details + declaration + e-signature; the signed card becomes
	the paperless GRC the desk views at arrival). The guest can attach a
	photo of their ID - camera capture or upload - stored privately."""
	if not id_type or not id_number.strip():
		frappe.throw("ID type and number are required.")
	res = _res_by_token(token)
	if res.precheckin_status == "Verified":
		frappe.throw("Check-in details were already verified by the desk.")
	if id_type != frappe.db.get_value("Guest", res.guest, "id_type"):
		from kamra.localization import validate_id_type
		validate_id_type(res.property, id_type)

	# a signed card requires the declaration to be accepted
	signed = bool(signature and str(signature).startswith("data:image"))
	if signed and not int(consent or 0):
		frappe.throw("Please accept the registration declaration to sign.")

	id_file = _save_id_image(res.guest, id_image) if id_image else None
	addr_file = (_save_id_image(res.guest, address_image,
	                            "address_proof_file")
	             if address_image else None)
	frappe.db.set_value("Guest", res.guest, {
		"id_type": id_type,
		"id_number": id_number.strip(),
		"email": email or None,
		"nationality": nationality or None,
		"address_line": address_line or None,
		"city": city or None,
		**({"id_file": id_file} if id_file else {}),
		**({"address_proof_file": addr_file} if addr_file else {}),
	})
	frappe.db.set_value("Reservation", res.name, {
		"precheckin_status": "Submitted",
		"precheckin_on": frappe.utils.now_datetime(),
		"eta": eta or None,
		"special_requests": special_requests or res.special_requests,
		"precheckin_signature": signature if signed else None,
		"precheckin_consent": 1 if int(consent or 0) else 0,
	})

	from kamra.savings import log_action
	log_action(
		action_type="self_checkin",
		reference_doctype="Reservation",
		reference_name=res.name,
		property=res.property,
		minutes_saved=8,
		rationale="Guest completed pre-arrival check-in online",
		agent_name="Self Check-in",
		channel="API",
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True, "reservation": res.name}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def precheckin_upload_id(token: str, data: str):
	"""The guest photographs their ID during pre-arrival check-in.

	Deliberately NOT Frappe's upload_file. That endpoint would need the
	site-wide `allow_guests_to_upload_files` setting, which opens
	unauthenticated upload to the whole site; on its guest branch it sets
	ignore_permissions and never sees a token, so it cannot tell whether this
	guest owns this booking; and it takes is_private from the client - i.e.
	it trusts the browser to protect an Aadhaar scan. Here the token is the
	gate, the rate limit is real, and privacy is not negotiable.

	Optional by design: nothing downstream requires a document. A guest with
	a cracked camera or a bad lobby connection must still be able to
	pre-register, so the submit gate never mentions this.
	"""
	from kamra.id_documents import store_id_document

	res = _res_by_token(token)
	if res.precheckin_status == "Verified":
		frappe.throw("The desk has already verified your check-in details.")

	with act_as(GUEST_AGENT):
		# owning the File as the agent matters: File.has_permission short-
		# circuits True for doc.owner, so a human owner would hand that
		# person a way in that skips the booking's own permission check
		store_id_document(res, data, source="Guest")

	from kamra.savings import log_action
	log_action(
		action_type="id_document_upload",
		reference_doctype="Reservation",
		reference_name=res.name,
		property=res.property,
		minutes_saved=3,
		rationale="Guest uploaded their ID photo at self check-in",
		agent_name="Self Check-in",
		channel="API",
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True}


# The governed writer: guest-initiated actions are always written as this user
# so a guest can never post directly.
GUEST_AGENT = AGENT_EMAIL


@frappe.whitelist(allow_guest=True)
def laundry_info(token: str):
	"""Laundry price list + stay context for the in-stay guest page.
	Read-only — the guest sees what things cost, never a folio."""
	res = _res_by_token(token)
	if res.status != "Checked In":
		frappe.throw("Laundry pickup is available once you're checked in.")
	guest = frappe.get_doc("Guest", res.guest)
	rates = frappe.get_all(
		"Laundry Rate",
		filters={"property": res.property, "disabled": 0},
		fields=["item_name", "service_type", "rate", "express_rate"],
		order_by="item_name asc, service_type asc",
	)
	from kamra.laundry import express_multiplier
	for r in rates:
		r["express_rate"] = r["express_rate"] or round(
			(r["rate"] or 0) * express_multiplier(res.property), 0)
	# is there already an open pickup for this room? (so the page can say so)
	pending = frappe.db.exists(
		"Laundry Order",
		{"room": res.room, "status": ["in", ["Requested", "Collected",
		                                     "In Process", "Ready"]]})
	return {
		"reservation": res.name,
		"room": res.room,
		"room_no": (res.room or "").split("-")[-1],
		"guest_name": guest.full_name,
		"property": res.property,
		"rates": rates,
		"has_open_order": bool(pending),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def request_guest_laundry(token: str, notes: str = "", express: int = 0):
	"""In-house guest asks housekeeping to pick their laundry up. Written on
	the guest's behalf by the governed agent — the guest never touches pricing
	or the folio; staff count and price the bag at the door (status
	'Requested', exactly where a staff-logged pickup lands)."""
	res = _res_by_token(token)
	if res.status != "Checked In":
		frappe.throw("Laundry pickup is available once you're checked in.")
	# don't stack duplicate open requests for the same room
	existing = frappe.db.exists(
		"Laundry Order", {"room": res.room, "status": "Requested"})
	if existing:
		return {"ok": True, "order": existing, "already": True}

	with act_as(GUEST_AGENT):
		doc = frappe.get_doc({
			"doctype": "Laundry Order",
			"property": res.property,
			"room": res.room,
			"reservation": res.name,
			"status": "Requested",
			"express": 1 if int(express or 0) else 0,
			"notes": (notes or "").strip()[:200] or None,
		})
		doc.insert()

	from kamra.savings import log_action
	log_action(
		action_type="guest_laundry_request",
		reference_doctype="Laundry Order",
		reference_name=doc.name,
		property=res.property,
		rationale=f"Guest requested laundry pickup for {res.room}",
		agent_name="Guest Self-Service",
		channel="API",
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	return {"ok": True, "order": doc.name}


TOO_MANY_GUESTS = "The property cannot accommodate the number of people requested."


def _child_ages(child_ages) -> list[int] | None:
	"""Ages from the request - a list, a JSON list or "3,8,13". None when the
	caller sent only a children count."""
	if child_ages in (None, "", []):
		return None
	if isinstance(child_ages, str):
		raw = child_ages.strip()
		child_ages = frappe.parse_json(raw) if raw.startswith("[") else raw.split(",")
	ages = []
	for a in child_ages:
		if str(a).strip() == "":
			continue
		age = cint(a)
		if age < 0 or age > 17:
			frappe.throw("Child ages must be between 0 and 17.")
		ages.append(age)
	return ages


def _party(rt_doc, adults, children, ages) -> tuple[int, int, int]:
	"""(adults, children, infants) for this room type: with ages, its own age
	bands decide; with only a count, every child is a child."""
	from kamra.pricing import party_by_age

	if cint(adults) < 1:
		frappe.throw("At least one adult is required.")
	if ages is None:
		return cint(adults), cint(children), 0
	return party_by_age(rt_doc, cint(adults), ages)


def _over_capacity_note(above: int) -> str:
	return (f"{above} guest{'s' if above != 1 else ''} above what it sleeps: "
	        "possible only if the group is happy to share beds. The property "
	        "confirms the arrangement and the price for them.")


def _advance_terms(prop, total: float, full_payment: bool = False) -> tuple[float, str]:
	"""What the guest pays online now, and a human label - computed from the
	property's CURRENT booking-payment policy. Snapshotted onto the booking so
	a later policy change never re-bills an existing guest. A season marked
	full payment (holidays, December) takes the whole amount whatever the
	usual advance."""
	mode = prop.get("booking_payment_mode") or "Pay at hotel"
	total = float(total or 0)
	sym = _public_locale(prop.name).get("currency_symbol", "") if prop.get("name") else ""
	if full_payment and mode != "Pay at hotel":
		return total, f"Full payment ({sym}{total:,.0f}) on booking for these dates"
	if mode == "Advance percent":
		pct = float(prop.get("advance_percent") or 0)
		due = round(total * pct / 100, 2)
		return due, f"{pct:g}% advance ({sym}{due:,.0f}) now, rest at the hotel"
	if mode == "Registration fee":
		due = min(float(prop.get("registration_fee") or 0), total)
		return due, f"{sym}{due:,.0f} registration fee now, rest at the hotel"
	if mode == "Full online":
		return total, "Full amount paid online"
	return 0.0, "Pay at the hotel"


def _payment_split(prop, total: float, full_payment: bool = False) -> dict:
	"""Server-computed split the booking page shows: what is due now and
	what is left to pay at the hotel. The browser never derives these."""
	total = float(total or 0)
	due, policy = _advance_terms(prop, total, full_payment)
	return {
		"advance_due": due,
		"balance_at_hotel": round(max(0.0, total - due), 2),
		"payment_policy": policy,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def book(property: str, room_type: str, check_in_date: str,
         check_out_date: str, guest_name: str, phone: str,
         email: str = "", adults: int = 2, children: int = 0,
         meal_plan: str = "", special_requests: str = "", addons=None,
         voucher_code: str = "", idempotency_key: str = "", pets: int = 0,
         child_ages=None, marketing_consent: int = 0):
	"""Create a Website booking. Guest identity is the phone number; staff
	verify at check-in. The advance owed is computed from the property's
	current payment policy and snapshotted onto the booking.

	Instant mode (default): Confirmed when nothing is due now, else
	Pending Payment with a hold window. Request to Book: Requested (no
	inventory) until the host approves. A party above what the room sleeps,
	within the extra guests it allows, is also Requested: the host confirms
	the sleeping arrangement and agrees the price for them.
	"""
	if not guest_name.strip() or not phone.strip():
		frappe.throw("Name and phone are required.")

	from kamra.pricing import capacity_overflow

	prop = frappe.get_cached_doc("Property", property)
	rtd = frappe.get_cached_doc("Room Type", room_type)
	adults, children, infants = _party(rtd, adults, children, _child_ages(child_ages))
	above, beds = capacity_overflow(rtd, adults, children)
	if above > beds:
		frappe.throw(TOO_MANY_GUESTS)

	# a guest may only add experiences the hotel actually publishes for this
	# property - never a private, disabled or another property's experience,
	# and always at the hotel's own price (qty is all the guest controls)
	if isinstance(addons, str):
		addons = frappe.parse_json(addons)
	public_ids = set(frappe.get_all(
		"Experience",
		filters={"property": property, "disabled": 0, "show_on_booking_page": 1},
		pluck="name",
	))
	safe_addons = [
		{"experience": a["experience"], "qty": max(1, int(a.get("qty") or 1))}
		for a in (addons or [])
		if a.get("experience") in public_ids
	]

	from kamra.api import create_booking
	from kamra.pricing import quote as price_quote
	from kamra.reservation_state import resolve_instant_status

	mode = getattr(prop, "booking_mode", None) or "Instant"
	hold_minutes = cint(getattr(prop, "hold_minutes", None) or 120)
	key = (idempotency_key or "").strip() or None

	# Peek at payment terms before insert so Instant can choose status.
	q = price_quote(
		property, room_type, check_in_date, check_out_date,
		int(adults), int(children), meal_plan or None,
		voucher_code=voucher_code or None, pets=int(pets or 0),
	)
	full_payment = bool((q.get("stay_rules") or {}).get("full_payment"))
	advance_due, policy = _advance_terms(
		prop, float(q["amount_after_tax"] or 0), full_payment)

	status = None
	hold_expires_on = None
	assign_room = 1
	if mode == "Request to Book" or above:
		status = "Requested"
		assign_room = 0
	else:
		status, hold_expires_on = resolve_instant_status(
			advance_due=advance_due, hold_minutes=hold_minutes,
		)

	with act_as(GUEST_AGENT):
		result = create_booking(
			property=property,
			room_type=room_type,
			check_in_date=check_in_date,
			check_out_date=check_out_date,
			guest_name=guest_name,
			phone=phone,
			adults=adults,
			# infants are on the booking but free and take no bed
			children=children + infants,
			stay_details={"infants": infants} if infants else None,
			over_capacity_guests=above,
			over_capacity_reason=(
				f"Booked online for {above} above capacity - the property "
				"confirms the sleeping arrangement and price") if above else None,
			pets=int(pets or 0),
			meal_plan=meal_plan or None,
			voucher_code=voucher_code or None,
			source="Website",
			addons=safe_addons or None,
			assign_room=assign_room,
			status=status,
			idempotency_key=key,
			hold_expires_on=str(hold_expires_on) if hold_expires_on else None,
		)
		# snapshot the advance owed from the policy in force RIGHT NOW, so a
		# later change to the property's payment config never re-bills this guest
		total = float(result["amount_after_tax"] or 0)
		# Recompute against the saved total (voucher / engine may differ).
		advance_due, policy = _advance_terms(prop, total, full_payment)
		updates = {
			"advance_due": advance_due,
			"payment_policy": policy,
			"is_pay_at_hotel": 1 if advance_due < total else 0,
		}
		if special_requests:
			updates["special_requests"] = special_requests
		# Instant + pay-at-hotel: if pre-insert peek overestimated advance,
		# promote Pending Payment → Confirmed.
		if (
			mode == "Instant"
			and not result.get("idempotent_replay")
			and result.get("status") == "Pending Payment"
			and advance_due <= 0
		):
			frappe.flags.kamra_status_transition = True
			try:
				updates["status"] = "Confirmed"
				updates["hold_expires_on"] = None
			finally:
				frappe.flags.kamra_status_transition = False
		frappe.db.set_value("Reservation", result["reservation"], updates)
		if email:
			frappe.db.set_value("Guest", result["guest"], "email", email)
		if cint(marketing_consent):
			# the guest ticked the (unticked by default) offers box
			from kamra.privacy import set_marketing_consent
			set_marketing_consent(result["guest"], 1, "Booking Page", property)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional

	final_status = frappe.db.get_value(
		"Reservation", result["reservation"], "status")
	return {
		"reservation": result["reservation"],
		"amount_after_tax": result["amount_after_tax"],
		"advance_due": advance_due,
		"balance_at_hotel": round(
			max(0.0, float(result["amount_after_tax"] or 0) - advance_due), 2),
		"payment_policy": policy,
		"pay_at_hotel": advance_due <= 0,
		"status": final_status,
		"needs_confirmation": bool(above),
		"confirmation_reason": _over_capacity_note(above) if above else None,
		"is_holiday": bool(q.get("is_holiday")),
		"idempotent_replay": int(result.get("idempotent_replay") or 0),
		"cleaning_fee": float(
			frappe.db.get_value("Property", property, "cleaning_fee") or 0
		),
		"security_deposit_amount": float(
			frappe.db.get_value("Property", property, "security_deposit_amount") or 0
		),
	}


@frappe.whitelist(allow_guest=True)
def access_info(token: str):
	"""Guest access instructions when gates pass (precheckin token)."""
	from kamra.access import guest_access_info
	return guest_access_info(token)


@frappe.whitelist(allow_guest=True)
def check_voucher(property: str, code: str, nights: int = 1):
	"""Live promo-code feedback on the booking page. Never throws - returns
	{ok, message, discount_type, value} so the guest sees a friendly note."""
	from kamra.pricing import validate_voucher
	code = (code or "").strip()
	if not code:
		return {"ok": False, "message": "Enter a code."}
	try:
		v = validate_voucher(property, code, int(nights or 1))
	except Exception as e:
		return {"ok": False, "message": str(e)}
	label = (f"{v.value:g}% off" if v.discount_type == "Percent"
	         else f"₹{v.value:,.0f} off")
	return {"ok": True, "message": f"'{v.voucher_code}' applied - {label}.",
	        "discount_type": v.discount_type, "value": float(v.value)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def hosting_enquiry(full_name: str, email: str, phone: str = "",
                    property_name: str = "", rooms: int = 0, city: str = "",
                    message: str = "", country: str = "",
                    interest: str = ""):
	"""Hosting / implementation enquiry from kamrapms.com. Stored first (a lead is
	never lost even without SMTP), then a best-effort email to the team.

	Leads are System Manager–only and purged after
	``hosting_enquiry_retention_months`` (default 24) unless status is Won.
	"""
	if not (full_name or "").strip() or not (email or "").strip():
		frappe.throw("Name and email are required.")
	doc = frappe.get_doc({
		"doctype": "Hosting Enquiry",
		"full_name": full_name.strip()[:140],
		"email": email.strip()[:140],
		"phone": (phone or "").strip()[:40] or None,
		"property_name": (property_name or "").strip()[:140] or None,
		"rooms": int(rooms or 0),
		"city": (city or "").strip()[:80] or None,
		"country": (country or "").strip()[:80] or None,
		"interest": (interest or "").strip()[:40]
		            if (interest or "").strip() in
		            ("Hosting", "Implementation", "Support AMC", "Partnership")
		            else None,
		"message": (message or "").strip()[:2000] or None,
		"status": "New",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists the completed operation before returning to an external/public caller; reviewed as intentional
	try:
		frappe.sendmail(
			recipients=["hello@kamrapms.com"],
			subject=f"Kamra {doc.interest or 'Cloud'} enquiry: {doc.full_name}"
			        + (f" ({doc.property_name})" if doc.property_name else ""),
			message=(
				f"<p><b>{doc.full_name}</b> &lt;{doc.email}&gt;"
				+ (f" · {doc.phone}" if doc.phone else "") + "</p>"
				+ (f"<p>Property: {doc.property_name}"
				   + (f", {doc.rooms} rooms" if doc.rooms else "")
				   + (f", {doc.city}" if doc.city else "") + "</p>"
				   if doc.property_name else "")
				+ (f"<p>{doc.message}</p>" if doc.message else "")
				+ f"<p>Ref: {doc.name}</p>"
			),
		)
	except Exception:
		pass  # no SMTP yet - the enquiry is already saved
	return {"ok": True,
	        "message": "Thanks - we'll get back to you within a day."}
