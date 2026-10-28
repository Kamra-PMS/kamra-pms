"""Settings hub - one registry for everything a property configures.

Each module (Front Desk, Housekeeping, F&B, ...) owns a page of settings.
A setting lives in one of three stores:

  property  - a field on the Property doc (identity, policies, tax slabs)
  kv        - a Property Setting row, for knobs that used to be constants
              (HK SLA minutes, PIN lockout, banquet margins, ...)
  turnover  - the property's default Turnover Profile

Code reads a value with `get_setting(property, key)`; the UI reads the
schema with `settings_schema` and writes with `save_settings`, which
checks the module's editor roles, validates against the registry and
logs every change to the Activity log. Nothing else should write these.
"""

import json
from dataclasses import dataclass, field

import frappe
from frappe import _

from kamra.authz import ADMIN, assert_property_access, require_roles

CACHE_KEY = "kamra_settings"


@dataclass(frozen=True)
class S:
	key: str
	label: str
	type: str = "text"  # text|number|time|check|select|textarea|image|email
	default: object = None
	store: str = "kv"  # property|kv|turnover
	hint: str = ""
	options: tuple = ()
	options_source: str = ""  # countries|timezones - filled by the client
	min: float | None = None
	max: float | None = None
	unit: str = ""  # shown after a number input: min, %, days, x


@dataclass(frozen=True)
class Section:
	id: str
	title: str
	description: str
	settings: tuple


@dataclass(frozen=True)
class Module:
	id: str  # = the app slug in enabled_modules where one exists
	title: str
	description: str
	editors: tuple  # roles that may change it (admins always may)
	sections: tuple = ()
	group: str = "modules"  # organisation|modules
	toggle: bool = False  # can be switched off in enabled_modules
	related: tuple = field(default_factory=tuple)  # (label, route)


P = "property"
SLA_HINT = "Minutes from creation until the task counts as overdue."

MODULES: tuple[Module, ...] = (
	# --- organisation ------------------------------------------------------
	Module(
		"general", "Property", "Identity, location and contact details - printed on invoices and the GRC.",
		editors=("Hotel Admin",), group="organisation",
		sections=(
			Section("identity", "Identity", "", (
				S("property_name", "Property name", store=P),
				S("legal_name", "Legal name", store=P, hint="As registered - printed on invoices."),
				S("property_kind", "Property kind", "select", store=P, options=("Hotel", "Short Term Rental")),
				S("logo_url", "Logo", "image", store=P, hint="Square, 512px+ - PNG or SVG with transparency looks best."),
			)),
			Section("location", "Location & locale", "Country selects the tax and invoicing pack.", (
				S("country", "Country", "select", store=P, options_source="countries",
				  hint="Tax labels, ID types, payment methods and the guest phone code follow it."),
				S("currency", "Currency", store=P, hint="ISO code, e.g. SAR, AED, USD."),
				S("timezone", "Time zone", "select", store=P, options_source="timezones",
				  hint="Hotel local clock for the night audit and timestamps."),
				S("address_line", "Address", store=P),
				S("city", "City", store=P),
				S("state", "State / region", store=P),
				S("pincode", "Postal code", store=P),
			)),
			Section("contact", "Contact & registration", "", (
				S("phone", "Phone", store=P),
				S("email", "Email", "email", store=P),
				S("website", "Website", store=P),
				S("gstin", "Tax registration number", store=P, hint="GSTIN, VAT or TRN - printed on invoices."),
			)),
		),
	),
	Module(
		"policies", "Stay policies", "Times, minimum stay and the money rules quoted at booking and enforced by cancel and the night audit.",
		editors=("Hotel Admin", "Revenue Manager"), group="organisation",
		sections=(
			Section("times", "Check-in & check-out", "", (
				S("checkin_time", "Check-in time", "time", "14:00", P),
				S("checkout_time", "Check-out time", "time", "11:00", P),
				S("minimum_nights", "Minimum stay", "number", 1, P, min=1, max=60, unit="nights"),
			)),
			Section("cancellation", "Cancellation & no-show", "", (
				S("free_cancel_days", "Free cancellation until", "number", 1, P, min=0, max=365, unit="days before",
				  hint="Cancellations earlier than this are always free."),
				S("cancellation_fee", "Late cancellation fee", "select", "First Night", P, options=("None", "First Night", "Full Stay")),
				S("no_show_charge", "No-show charge", "select", "First Night", P, options=("None", "First Night", "Full Stay"),
				  hint="Posted automatically by the night audit."),
			)),
			Section("deposits", "Deposits", "", (
				S("deposit_pct", "Deposit expected at booking", "number", 0, P, min=0, max=100, unit="%"),
				S("security_deposit_amount", "Security deposit", "number", 0, P, min=0),
			)),
		),
	),
	Module(
		"privacy", "Privacy & data", "How long guest data is kept and who guests contact about it.",
		editors=("Hotel Admin",), group="organisation",
		sections=(
			Section("retention", "Retention", "", (
				S("id_retention", "Guest ID retention", "select", "Verify & Discard", P, options=("Store", "Verify & Discard"),
				  hint="Verify & Discard masks ID numbers to the last 4 digits and deletes ID photos at checkout."),
				S("guest_retention_months", "Erase guest data after", "number", 36, P, min=0, unit="months",
				  hint="Guests with no stay for this long are erased; bills stay for the books. 0 keeps them."),
				S("message_retention_days", "Clear message text after", "number", 90, P, min=0, unit="days",
				  hint="WhatsApp and AI chat text is cleared nightly; who, when and delivery status stay. 0 keeps them."),
			)),
			Section("contact", "Grievance contact", "", (
				S("privacy_contact", "Privacy contact", store=P,
				  hint="Email or phone for access, correction or erasure requests - shown on booking and check-in pages."),
			)),
		),
	),
	# --- modules -----------------------------------------------------------
	Module(
		"front-desk", "Front Desk", "Arrivals, holds, no-shows and the day view.",
		editors=("Hotel Admin",),
		related=(("Rooms", "/rooms"), ("Room types", "/room-types")),
		sections=(
			Section("arrivals", "Arrivals", "Getting guests checked in before they reach the desk.", (
				S("auto_send_checkin_links", "Send pre-check-in links automatically", "check", 0, P,
				  hint="Guests arriving soon get their online check-in link each morning."),
				S("prearrival_horizon_days", "Send links this far ahead", "number", 2, min=1, max=14, unit="days"),
				S("require_precheckin_for_access", "Require pre-check-in before access details", "check", 0, P),
				S("access_instructions", "Access instructions", "textarea", store=P,
				  hint="Door codes, parking, Wi-Fi. Released only after payment, deposit and (if set) pre-check-in."),
			)),
			Section("door_locks", "Door locks", "How room keys are issued at check-in and cancelled at check-out.", (
				S("door_lock_adapter", "Door lock system", "select", "manual",
				  options=("manual",),
				  hint="Manual: staff encode key cards at the lock's own encoder. Lock vendor "
				       "connectors plug in here (see the integrations docs)."),
			)),
			Section("guest_info", "Guest info at check-in",
			        "Shown to the desk in the check-in steps, to tell the guest, print or send on WhatsApp.", (
				S("guest_wifi_name", "Wi-Fi name"),
				S("guest_wifi_password", "Wi-Fi password",
				  hint="Shown to the desk and given to guests. Never written to the activity log."),
				S("breakfast_hours", "Breakfast times", hint="For example: 7:00 to 10:30, ground floor restaurant."),
				S("emergency_number", "Emergency number", hint="Reception or duty manager, day and night."),
				S("guest_info_note", "Anything else for guests", "textarea",
				  hint="Pool hours, parking, quiet hours. Keep it short."),
			)),
			Section("holds", "Holds & selling", "", (
				S("hold_minutes", "Hold unconfirmed bookings for", "number", 120, P, min=5, max=10080, unit="min"),
				S("sell_message", "Sell message", "textarea", store=P,
				  hint="Shown in the booking dialog and used by the AI agent as its upsell prompt."),
			)),
			Section("noshow", "Night audit & no-shows",
			        "When the night audit turns an arrival that never came into a No Show, and who pays for it. "
			        "The fee itself is the no-show charge under Stay policies.", (
				S("no_show_timing", "Mark no-shows", "select", "At audit for arrival date", P,
				  options=("At audit for arrival date", "One day later"),
				  hint="At audit for arrival date: the audit closing the arrival date marks it. "
				       "One day later: the arrival stays Due In until the next day's audit."),
				S("protect_late_arrivals", "Hold late arrivals until the next audit", "check", 1, P,
				  hint="An arrival due on the day being closed stays Due In if it is flagged Late arrival, "
				       "or its ETA is later than the moment the audit runs (property time; an ETA before "
				       "06:00 means after midnight). The next audit marks it a no-show if it still has not arrived."),
				S("waive_no_show_fee_for_ota", "No no-show fee on OTA bookings", "check", 1, P,
				  hint="Bookings from an OTA or channel are still marked No Show, but no fee is posted - "
				       "the OTA charges the guest under its own policy."),
				S("non_guaranteed_release_time", "Release non-guaranteed arrivals at", "time", None, P,
				  hint="Leave blank to never release. At this time, today's arrivals with no advance, "
				       "payment or deposit on the folio, and that are not an OTA or company booking, "
				       "are cancelled with no fee and the room goes back on sale. Late arrivals and "
				       "bookings made after this time are kept."),
			)),
			Section("nightaudit", "Automatic night audit",
			        "When the scheduler closes the business date. It runs on the property's "
			        "time zone (Property settings) and closes one day per run.", (
				S("night_audit_auto", "Run the night audit automatically", "check", 1,
				  hint="Off: the scheduler never closes this property; staff close the day "
				       "from End of Day."),
				S("night_audit_time", "Run at", "time", "03:00",
				  hint="Property local time. Checked every 15 minutes, so the audit starts "
				       "within 15 minutes of this time."),
				S("night_audit_grace_minutes", "Wait after that time", "number", 0,
				  min=0, max=120, unit="min",
				  hint="Extra delay, for a bar or restaurant still posting after the set time."),
			)),
			Section("auditchecks", "Night audit checklist",
			        "Checks run before the night audit closes the day (Finance → End of Day). "
			        "A blocking check stops a manual run until it is resolved or a supervisor "
			        "acknowledges it with a reason; a warning is listed in the audit pack only.", (
				S("na_block_open_tills", "Open tills block the audit", "check", 1,
				  hint="Cashier sessions not yet closed (cash counted) for the business date. "
				       "Off: listed as a warning."),
				S("na_block_open_pos", "Open restaurant bills block the audit", "check", 1,
				  hint="POS bills still open, or served and neither paid nor posted to a room. "
				       "Off: listed as a warning."),
				S("na_block_departures", "Departures still in house block the audit", "check", 1,
				  hint="Guests due out on the business date who are still Checked In: check them "
				       "out or extend the stay. Off: listed as a warning."),
				S("na_high_balance_threshold", "Flag in-house folios owing more than", "number", 50000,
				  min=0, hint="0 turns the high-balance check off."),
				S("na_rate_variance_tolerance", "Rate variance tolerance", "number", 1.0,
				  min=0, max=100000,
				  hint="A room night posted more than this away from the booked (locked) "
				       "nightly rate is listed as a rate variance."),
				S("na_auto_audit_with_blockers", "Scheduled audit when checks block", "select",
				  "Run and report exceptions",
				  options=("Run and report exceptions", "Hold and alert"),
				  hint="Run and report exceptions: the date always rolls; open items go in the "
				       "audit pack as exceptions. Hold and alert: the business date is not "
				       "rolled and Hotel Admin and Finance are alerted."),
			)),
			Section("dayview", "Hourly view", "The time window on the day-use / hourly tape.", (
				S("hourly_view_start", "Day starts", "time", "06:00", P),
				S("hourly_view_end", "Day ends", "time", "23:00", P),
			)),
		),
	),
	Module(
		"housekeeping", "Housekeeping", "Task deadlines, room turnover and laundry pricing.",
		editors=("Hotel Admin", "Housekeeping Supervisor"), toggle=True,
		related=(("Laundry orders", "/laundry"), ("Room board", "/housekeeping-board")),
		sections=(
			Section("sla", "Task deadlines", "How long a housekeeping task may stay open before it is overdue and escalates.", (
				S("hk_sla_urgent", "Urgent", "number", 20, min=1, max=1440, unit="min", hint=SLA_HINT),
				S("hk_sla_high", "High", "number", 45, min=1, max=1440, unit="min"),
				S("hk_sla_medium", "Medium", "number", 90, min=1, max=1440, unit="min"),
				S("hk_sla_low", "Low", "number", 180, min=1, max=2880, unit="min"),
			)),
			# Only knobs that code acts on live here. Clean duration, the
			# sellable buffer and same-day turns are fields on the Turnover
			# Profile, but nothing reads them yet - showing them would promise
			# behaviour that doesn't exist.
			Section("turnover", "Room turnover", "Inspection after checkout cleans.", (
				S("requires_inspection", "Inspect after every checkout clean", "check", 0, "turnover",
				  hint="When a checkout clean is done, a supervisor inspection task is created. "
				       "Passing it marks the room Ready."),
				S("inspect_duration_minutes", "Inspection takes", "number", 30, "turnover", min=5, max=480, unit="min",
				  hint="The inspection task is due this long after the clean is done."),
			)),
			Section("laundry", "Laundry", "", (
				S("laundry_express_multiplier", "Express price", "number", 1.5, min=1, max=5, unit="x regular",
				  hint="Used when a rate card line leaves its express price blank."),
			)),
		),
	),
	Module(
		"operations", "Operations", "Guest request deadlines.",
		editors=("Hotel Admin",), toggle=True,
		related=(("Channels", "/channels"), ("SLA report", "/ops-sla")),
		sections=(
			Section("sla", "Guest request deadlines", "How long a guest request may stay open before it is overdue.", (
				S("ticket_sla_urgent", "Urgent", "number", 15, min=1, max=1440, unit="min"),
				S("ticket_sla_high", "High", "number", 30, min=1, max=1440, unit="min"),
				S("ticket_sla_medium", "Medium", "number", 60, min=1, max=1440, unit="min"),
				S("ticket_sla_low", "Low", "number", 240, min=1, max=2880, unit="min"),
			)),
		),
	),
	Module(
		"fnb", "F&B", "Restaurant outlets, the menu and table reservations.",
		editors=("Hotel Admin", "Finance"), toggle=True,
		related=(("Outlets", "/outlets"), ("Menu", "/menu-items"), ("Ingredients", "/ingredients"),
		         ("Kitchen inventory", "/inventory"),
		         ("Kitchen display", "/kitchen"), ("Printers", "/printers")),
		sections=(
			Section("kot", "Kitchen orders (KOT)", "What happens when a captain sends an order to the kitchen.", (
				S("pos_auto_kot", "Auto-accept and print KOT", "check", 0,
				  hint="On: sending an order prints the KOT and shows it on the kitchen display as "
				       "started, so nobody presses Start. Off: the kitchen presses Start and each till "
				       "chooses whether to print. An outlet can override this on its own record."),
				S("pos_print_void_slips", "Print void slips in the kitchen", "check", 1,
				  hint="A line voided or an order cancelled after its KOT was sent prints a VOID "
				       "slip on the kitchen printer that had it, so the cook stops."),
				S("pos_unfired_alert_min", "Flag a bill not sent to the kitchen after", "number", 15,
				  min=1, max=240, unit="min",
				  hint="A bill with items that nobody sent to the kitchen turns red on the till "
				       "after this long, so a forgotten order gets sent or cancelled."),
			)),
			Section("tables", "Table reservations", "Which bookings show against a table on the POS floor.", (
				S("pos_reservation_before_min", "Show a reservation from", "number", 60, min=0, max=480, unit="min before"),
				S("pos_reservation_after_min", "Keep showing it until", "number", 240, min=0, max=720, unit="min after"),
			)),
			Section("external_pos", "External POS", "A third-party POS posting room charges through the POS interface.", (
				S("pos_room_charge_limit", "Largest room charge from an external POS", "number", 0, min=0,
				  hint="One ticket above this is refused - settle it at the outlet. 0 means no limit."),
			)),
			Section("menu_masters", "Menu master lists",
			        "Labels used when adding a dish. Edit here once; every New Menu form and the kitchen use them.", (
				S("menu_allergen_tags", "Allergens & dietary tags", "textarea",
				  "Egg\nDairy\nNuts\nPeanuts\nGluten\nSoy\nShellfish\nFish\nSesame\nSulphites",
				  hint="One per line. Shown as chips on each menu item (Egg, Nuts, …). Matched against the guest's allergy note on the kitchen display."),
				S("menu_prep_stations", "Prep stations", "textarea",
				  "Kitchen\nTandoor\nGrill\nFryer\nBar",
				  hint="One per line. Which KOT a dish prints to, and how the kitchen display groups tickets."),
				S("menu_courses", "Courses", "textarea",
				  "Starter\nMain\nDessert\nDrink",
				  hint="One per line. Serving order on the kitchen display (starters before mains)."),
				S("menu_categories", "Menu categories", "textarea",
				  "Starters\nMains\nBreads\nRice\nDesserts\nBeverages\nBar",
				  hint="One per line. Suggestions when typing a category on a menu item - free text still allowed."),
			)),
		),
	),
	Module(
		"events", "Banquets & Groups", "Quotation margins, payment milestones and follow-ups for functions.",
		editors=("Hotel Admin", "Revenue Manager"), toggle=True,
		related=(("Halls & venues", "/venues"), ("Menus & services", "/banquet-catalogue")),
		sections=(
			Section("margins", "Quotation margins", "Function quotes are checked against these before they go out.", (
				S("banquet_target_margin", "Target margin", "number", 40, min=0, max=95, unit="%"),
				S("banquet_floor_margin", "Floor margin", "number", 25, min=0, max=95, unit="%",
				  hint="Quotes below this are flagged for approval."),
			)),
			Section("payments", "Default payment milestones", "Applied to a new function; each can be changed on the function.", (
				S("banquet_advance_pct", "Advance at confirmation", "number", 25, min=0, max=100, unit="%"),
				S("banquet_interim_pct", "Interim payment", "number", 50, min=0, max=100, unit="%"),
				S("banquet_interim_days", "Interim due", "number", 15, min=0, max=365, unit="days before"),
			)),
			Section("followup", "Sales follow-up", "", (
				S("banquet_follow_up_days", "Follow up an enquiry after", "number", 2, min=0, max=60, unit="days"),
			)),
		),
	),
	Module(
		"revenue", "Revenue", "How far the house may oversell, plus demand pricing.",
		editors=("Hotel Admin", "Revenue Manager"), toggle=True,
		related=(("Rate plans", "/rate-plans"), ("Seasons", "/seasons"), ("Guardrails", "/guardrails")),
		sections=(
			Section("inventory", "Overbooking", "", (
				S("overbooking_pct", "Overbooking allowance", "number", 0, P, min=0, max=50, unit="%",
				  hint="0 never oversells. A room type can override this."),
			)),
		),
	),
	Module(
		"finance", "Finance", "Room tax, fees, company credit and cashier controls.",
		editors=("Hotel Admin", "Finance"), toggle=True,
		related=(("Currency desk", "/cashier/fx"), ("Ledgers", "/ledgers"),
		         ("Transaction codes", "/transaction-codes"), ("Reason codes", "/reason-codes")),
		sections=(
			Section("tax", "Room tax", "Tax on the room rate. Outlet and service rates come from the country pack.", (
				S("gst_mode", "Tax mode", "select", "Slab", P, options=("Slab", "Fixed"),
				  hint="Slab: the rate switches at the threshold per night."),
				S("gst_slab_threshold", "Slab threshold per night", "number", 7500, P, min=0),
				S("gst_rate_low", "Rate below threshold", "number", 5, P, min=0, max=100, unit="%"),
				S("gst_rate_high", "Rate above threshold", "number", 18, P, min=0, max=100, unit="%"),
				S("rates_include_tax", "Displayed rates include tax", "check", 0, P),
			)),
			Section("fees", "Fees & levies", "", (
				S("room_levy_label", "Room levy name", store=P, hint="Municipality fee, city or tourism tax."),
				S("room_levy_percent", "Room levy", "number", 0, P, min=0, max=100, unit="%"),
				S("room_levy_taxable", "Tax applies to the levy", "check", 1, P),
				S("cleaning_fee", "Cleaning fee per stay", "number", 0, P, min=0),
				S("cleaning_fee_taxable", "Cleaning fee is taxable", "check", 1, P),
				S("pets_allowed", "Pets allowed", "check", 0, P,
				  hint="Shows a Pets count on the booking pages and the desk booking form."),
				S("pet_charge", "Pet charge", "number", 0, P, min=0,
				  hint="Per pet, taxed at the room's rate. 0 lets pets stay free."),
				S("pet_charge_basis", "Pet charge applies", "select", "Per stay", P,
				  options=("Per stay", "Per night")),
			)),
			Section("corporate", "Corporate billing",
			        "Who pays what on a credit company's stay when that company has no billing rules of its own. "
			        "A company's own rules always win, and liquor never bills to a company.", (
				S("default_company_billing", "When a credit company has no billing rules", "select",
				  "Room and F&B (liquor to guest)", P,
				  options=("Room and F&B (liquor to guest)", "Room only", "Everything except liquor",
				           "Nothing (guest pays unless rules say so)"),
				  hint="Room covers the room night, its meal plan, levies, early check-in / late checkout and the "
				       "cleaning fee. Laundry, minibar, spa and misc extras stay with the guest unless "
				       "'Everything except liquor' is chosen."),
			)),
			Section("credit", "Company credit",
			        "Payment terms and credit control for companies billed on the city ledger. "
			        "The check runs when a stay is booked on company billing and when a bill moves to the "
			        "city ledger at check-out. Set each company's credit limit and credit days on its "
			        "corporate account.", (
				S("default_credit_days", "Default payment terms", "number", 30, min=0, max=365, unit="days",
				  hint="Days after the invoice date a company bill is due, for companies set to use the property "
				       "default (the default for every company). 0 means due on the invoice date."),
				S("credit_control", "Credit control", "select", "Warn", options=("Off", "Warn", "Block"),
				  hint="Checks the credit limit and overdue bills. Warn: the desk sees a warning and can go "
				       "ahead. Block: refused unless Finance or a Hotel Admin overrides it with a reason, "
				       "which is logged. AI agents can never override."),
				S("credit_overdue_grace_days", "Overdue grace period", "number", 0, min=0, max=365, unit="days",
				  hint="A bill counts against the company only once it is this many days past its due date."),
				S("credit_reminders", "Email payment reminders", "check", 0,
				  hint="Each morning, email a company's billing contact 3 days before a bill is due, on the "
				       "due date and 15 days after, with its statement attached. Each reminder goes once per "
				       "bill, and Finance gets a notice of what was sent."),
			)),
			Section("cashier", "Cashier controls", "", (
				S("use_cashier_tills", "Take money through cashier tills", "check", 1,
				  hint="On: staff open their till (with an opening float) before taking or giving back "
				       "money, and close it with a cash count. Off, for a small place with no cash drawer: "
				       "payments and refunds are recorded without a till."),
				S("require_cashier_pin", "Require cashier PIN on money actions", "check", 0, P,
				  hint="Payments, invoices, allowances and settlements re-confirm who is acting. Agents are exempt."),
				S("pin_max_attempts", "Lock a PIN after", "number", 5, min=3, max=10, unit="wrong tries"),
				S("pin_lock_minutes", "Lock for / stay unlocked for", "number", 15, min=1, max=240, unit="min"),
				S("max_cash_refund", "Cash refund limit for new cashiers", "number", 5000, min=0),
				S("till_variance_tolerance", "Till variance that needs a manager", "number", 0, min=0,
				  hint="A till closed over or short by more than this is flagged for a manager to review. 0 turns the check off."),
			)),
		),
	),
	Module(
		"booking-engine", "Booking Engine", "The public /book page: on or off, how it confirms and how guests pay.",
		editors=("Hotel Admin", "Revenue Manager"), toggle=True,
		related=(("Hotel profile", "/booking-settings/profile"), ("Photos", "/booking-settings/photos"),
		         ("FAQ", "/booking-settings/faq"), ("SEO", "/booking-settings/seo")),
		sections=(
			Section("page", "Booking page", "", (
				S("booking_engine_enabled", "Public booking page is live", "check", 1, P),
				S("booking_mode", "Booking mode", "select", "Instant", P, options=("Instant", "Request to Book")),
			)),
			Section("payment", "Guest payment", "", (
				S("booking_payment_mode", "Guests pay", "select", "Pay at hotel", P,
				  options=("Pay at hotel", "Advance percent", "Registration fee", "Full online")),
				S("advance_percent", "Advance", "number", 0, P, min=0, max=100, unit="%",
				  hint="Used when guests pay an advance percent."),
				S("registration_fee", "Registration fee", "number", 0, P, min=0,
				  hint="Used when guests pay a registration fee."),
			)),
		),
	),
)

BY_ID = {m.id: m for m in MODULES}
SETTINGS: dict[str, tuple[Module, S]] = {
	s.key: (m, s) for m in MODULES for sec in m.sections for s in sec.settings
}
assert len(SETTINGS) == sum(len(sec.settings) for m in MODULES for sec in m.sections), \
	"duplicate setting key in the registry"


# --- reading -----------------------------------------------------------------

def clear_cache(property: str | None = None):
	if property:
		frappe.cache().hdel(CACHE_KEY, property)
	else:
		frappe.cache().delete_key(CACHE_KEY)


def _kv_values(property: str) -> dict:
	cached = frappe.cache().hget(CACHE_KEY, property)
	if cached is not None:
		return cached
	rows = frappe.get_all("Property Setting", filters={"property": property},
	                      fields=["setting_key", "value"])
	out = {}
	for r in rows:
		try:
			out[r.setting_key] = json.loads(r.value)
		except (TypeError, ValueError):
			out[r.setting_key] = r.value
	frappe.cache().hset(CACHE_KEY, property, out)
	return out


def read_kv(property: str, key: str, default=None):
	"""A Property Setting value that is not a registry field (a structured
	value like the Today layout). Cached with the registry values."""
	val = _kv_values(property).get(key)
	return default if val is None else val


def write_kv(property: str, key: str, val):
	"""The one writer of a Property Setting row. Callers check roles and
	log the change; this stores the JSON value and nothing else. The
	caller clears the cache (clear_cache) once it is done writing."""
	name = frappe.db.get_value("Property Setting", {"property": property, "setting_key": key})
	if name:
		frappe.db.set_value("Property Setting", name, "value", json.dumps(val))
	else:
		frappe.get_doc({"doctype": "Property Setting", "property": property,
		                "setting_key": key, "value": json.dumps(val)}).insert(ignore_permissions=True)


def _turnover_name(property: str) -> str | None:
	if not frappe.db.exists("DocType", "Turnover Profile"):
		return None
	return frappe.db.get_value("Turnover Profile", {"property": property, "is_default": 1}, "name")


def get_setting(property: str | None, key: str, default=None):
	"""The value of one registry setting for a property, or its default.
	Safe to call from anywhere (scheduler, hooks) - never raises on a
	missing property or row."""
	_, spec = SETTINGS[key]
	fallback = spec.default if default is None else default
	if not property:
		return fallback
	try:
		if spec.store == "kv":
			val = _kv_values(property).get(key)
		elif spec.store == "property":
			val = frappe.db.get_value("Property", property, key)
		else:
			name = _turnover_name(property)
			val = frappe.db.get_value("Turnover Profile", name, key) if name else None
	except Exception:
		return fallback
	if val is None or val == "":
		return fallback
	return _coerce(spec, val)


def parse_list(raw) -> list[str]:
	"""Split a master-list setting (textarea: one per line, or commas) into
	trimmed unique labels, keeping first-seen order."""
	if raw is None or raw == "":
		return []
	if isinstance(raw, (list, tuple)):
		parts = [str(x) for x in raw]
	else:
		parts = str(raw).replace(",", "\n").splitlines()
	out, seen = [], set()
	for p in parts:
		label = p.strip()
		if not label:
			continue
		key = label.casefold()
		if key in seen:
			continue
		seen.add(key)
		out.append(label)
	return out


def list_setting(property: str | None, key: str) -> list[str]:
	"""A registry textarea/text setting as an ordered list of labels."""
	return parse_list(get_setting(property, key))


def _coerce(spec: S, val):
	if spec.type == "number":
		f = float(val)
		return int(f) if f.is_integer() and not isinstance(spec.default, float) else f
	if spec.type == "check":
		return 1 if val in (1, "1", True, "true") else 0
	if spec.type == "time":
		parts = str(val).split(":")
		return f"{int(parts[0]):02d}:{parts[1][:2] if len(parts) > 1 else '00'}"
	return val


def _values(property: str, module: Module) -> dict:
	keys = [s for sec in module.sections for s in sec.settings]
	prop_fields = [s.key for s in keys if s.store == P]
	prop = frappe.db.get_value("Property", property, prop_fields, as_dict=True) if prop_fields else {}
	turnover = None
	if any(s.store == "turnover" for s in keys):
		name = _turnover_name(property)
		turnover = frappe.db.get_value("Turnover Profile", name,
		                               [s.key for s in keys if s.store == "turnover"],
		                               as_dict=True) if name else {}
	kv = _kv_values(property)
	out = {}
	for s in keys:
		raw = (prop or {}).get(s.key) if s.store == P else \
			(turnover or {}).get(s.key) if s.store == "turnover" else kv.get(s.key)
		out[s.key] = s.default if raw is None or raw == "" else _coerce(s, raw)
	return out


# --- access ------------------------------------------------------------------

def _roles() -> set:
	return set(frappe.get_roles())


def can_edit(module: Module, roles: set | None = None) -> bool:
	roles = roles if roles is not None else _roles()
	return bool(roles & (set(ADMIN) | set(module.editors)))


def _enabled_modules(property: str) -> list:
	from kamra.api import ALL_MODULES
	raw = frappe.db.get_value("Property", property, "enabled_modules")
	picked = [m.strip() for m in (raw or "").split(",") if m.strip()]
	return picked or list(ALL_MODULES)


# --- endpoints ---------------------------------------------------------------

def _spec_json(s: S) -> dict:
	d = {"key": s.key, "label": s.label, "type": s.type, "default": s.default,
	     "hint": s.hint, "store": s.store}
	for k in ("options", "options_source", "min", "max", "unit"):
		v = getattr(s, k)
		if v not in (None, "", ()):
			d[k] = list(v) if isinstance(v, tuple) else v
	return d


@frappe.whitelist()
@require_roles("Finance", "Front Desk", "Night Auditor", "Kamra Agent")
def menu_masters(property: str) -> dict:
	"""Allergen tags, prep stations, courses and category suggestions for
	the Menu form and kitchen display. Edited under Settings → F&B → Menu
	master lists."""
	assert_property_access(property)
	return {
		"allergens": list_setting(property, "menu_allergen_tags"),
		"prep_stations": list_setting(property, "menu_prep_stations"),
		"courses": list_setting(property, "menu_courses"),
		"categories": list_setting(property, "menu_categories"),
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping",
               "Housekeeping Supervisor")
def settings_schema(property: str) -> dict:
	"""Every settings page this user may see for the property, with current
	values. Pages they can't change come back read-only (can_edit=False)."""
	assert_property_access(property)
	roles = _roles()
	enabled = _enabled_modules(property)
	modules = []
	for m in MODULES:
		editable = can_edit(m, roles)
		if not editable:
			continue
		modules.append({
			"id": m.id, "title": m.title, "description": m.description,
			"group": m.group, "toggle": m.toggle,
			"enabled": (m.id in enabled) if m.toggle else True,
			"editors": list(m.editors), "can_edit": editable,
			"related": [{"label": a, "to": b} for a, b in m.related],
			"sections": [{"id": sec.id, "title": sec.title, "description": sec.description,
			              "settings": [_spec_json(s) for s in sec.settings]} for sec in m.sections],
			"values": _values(property, m),
		})
	return {
		"modules": modules,
		"enabled_modules": enabled,
		"is_admin": bool(roles & set(ADMIN)),
		"is_it_admin": bool(roles & {"System Manager", "Administrator"}),
	}


def _validate(spec: S, val):
	if spec.type == "check":
		return 1 if val in (1, "1", True, "true") else 0
	if spec.type == "number":
		if val in (None, ""):
			return spec.default
		try:
			num = float(val)
		except (TypeError, ValueError):
			frappe.throw(_("{0} must be a number.").format(_(spec.label)))
		if spec.min is not None and num < spec.min:
			frappe.throw(_("{0} can't be below {1}.").format(_(spec.label), spec.min))
		if spec.max is not None and num > spec.max:
			frappe.throw(_("{0} can't be above {1}.").format(_(spec.label), spec.max))
		return int(num) if num.is_integer() and not isinstance(spec.default, float) else num
	if spec.type == "select" and spec.options and val not in spec.options and val not in ("", None):
		frappe.throw(_("{0}: pick one of {1}.").format(_(spec.label), ", ".join(spec.options)))
	if spec.type == "time" and val:
		try:
			h, mnt = str(val).split(":")[:2]
			assert 0 <= int(h) < 24 and 0 <= int(mnt) < 60
		except Exception:
			frappe.throw(_("{0} must be a time like 14:00.").format(_(spec.label)))
		return f"{int(h):02d}:{int(mnt):02d}"
	return "" if val is None else val


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Revenue Manager", "Housekeeping Supervisor")
def save_settings(property: str, module: str, changes) -> dict:
	"""Change some settings on one module page. Validates every key against
	the registry, refuses keys from another module, and writes one
	Activity log row with the before/after values."""
	assert_property_access(property)
	if isinstance(changes, str):
		changes = json.loads(changes or "{}")
	mod = BY_ID.get(module)
	if not mod:
		frappe.throw(_("Unknown settings page: {0}").format(module))
	if not can_edit(mod):
		frappe.throw(_("Your role can't change {0} settings.").format(_(mod.title)),
		             frappe.PermissionError)
	if not frappe.db.exists("Property", property):
		frappe.throw(_("Unknown property."))

	before_all = _values(property, mod)
	clean: dict = {}
	for key, val in (changes or {}).items():
		owner = SETTINGS.get(key)
		if not owner or owner[0].id != module:
			frappe.throw(_("{0} isn't a setting on this page.").format(key))
		clean[key] = _validate(owner[1], val)
	if not clean:
		return {"ok": True, "values": before_all}

	by_store: dict[str, dict] = {}
	for key, val in clean.items():
		by_store.setdefault(SETTINGS[key][1].store, {})[key] = val

	if by_store.get(P):
		doc = frappe.get_doc("Property", property)
		doc.update(by_store[P])
		doc.save(ignore_permissions=True)  # role checked above; controller validation still runs
	if by_store.get("turnover"):
		from kamra.turnover import ensure_default_profile
		name = ensure_default_profile(property)
		if name:
			tp = frappe.get_doc("Turnover Profile", name)
			tp.update(by_store["turnover"])
			tp.save(ignore_permissions=True)
	for key, val in (by_store.get("kv") or {}).items():
		write_kv(property, key, val)
	clear_cache(property)

	after_all = _values(property, mod)
	changed = {k: after_all[k] for k in clean if before_all.get(k) != after_all.get(k)}
	if changed:
		from kamra.savings import log_action
		labels = ", ".join(SETTINGS[k][1].label for k in changed)
		log_action("settings_changed", "Property", property, property=property,
		           rationale=f"{mod.title} settings: {labels}",
		           before_snapshot={k: before_all.get(k) for k in changed},
		           after_snapshot=changed)
	if "country" in changed or "currency" in changed:
		frappe.clear_cache()
	return {"ok": True, "values": after_all, "changed": list(changed)}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin")
def set_module_enabled(property: str, module: str, enabled) -> dict:
	"""Switch one module on or off for the property."""
	from kamra.api import set_enabled_modules
	mod = BY_ID.get(module)
	if not mod or not mod.toggle:
		frappe.throw(_("{0} can't be switched off.").format(module))
	on = str(enabled).lower() in ("1", "true")
	current = set(_enabled_modules(property))
	current = current | {module} if on else current - {module}
	res = set_enabled_modules(property, sorted(current))
	from kamra.savings import log_action
	log_action("module_enabled" if on else "module_disabled", "Property", property,
	           property=property, rationale=f"{mod.title} switched {'on' if on else 'off'}")
	return res
