"""One-time bootstrap: create Kamra's v0 DocTypes.

Run with:
    bench --site kamra.localhost execute kamra.scripts.bootstrap_schema.execute

Inserting DocType docs with developer_mode=1 writes the JSON + controller
boilerplate into this app, so the schema lands in git like hand-made files.
Idempotent: skips any DocType that already exists.
"""

import frappe

MODULE = "Kamra"


def _dt(name, fields, *, autoname=None, title_field=None, naming_rule=None,
        track_changes=1, extra=None):
    if frappe.db.exists("DocType", name):
        print(f"skip (exists): {name}")
        return
    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": name,
        "module": MODULE,
        "custom": 0,
        "is_submittable": 0,
        "track_changes": track_changes,
        "autoname": autoname,
        "naming_rule": naming_rule,
        "title_field": title_field,
        "engine": "InnoDB",
        "fields": fields,
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1,
             "delete": 1, "report": 1, "export": 1, "print": 1, "email": 1},
        ],
        **(extra or {}),
    })
    doc.insert(ignore_permissions=True)
    print(f"created: {name}")


def f(fieldname, fieldtype, label=None, **kw):
    d = {"fieldname": fieldname, "fieldtype": fieldtype,
         "label": label or fieldname.replace("_", " ").title()}
    d.update(kw)
    return d


def execute():
    frappe.flags.in_migrate = False

    # ── Property ─────────────────────────────────────────────────────────
    _dt("Property", [
        f("property_name", "Data", reqd=1, unique=1),
        f("legal_name", "Data"),
        f("column_break_a", "Column Break"),
        f("phone", "Data", options="Phone"),
        f("email", "Data", options="Email"),
        f("website", "Data"),
        f("sb_address", "Section Break", label="Address"),
        f("address_line", "Data"),
        f("city", "Data"),
        f("state", "Data"),
        f("column_break_b", "Column Break"),
        f("country", "Data", default="India"),
        f("pincode", "Data"),
        f("timezone", "Data", default="Asia/Kolkata"),
        f("sb_ops", "Section Break", label="Operations"),
        f("currency", "Link", options="Currency", default="INR"),
        f("checkin_time", "Time", label="Check-in Time", default="14:00:00"),
        f("checkout_time", "Time", label="Check-out Time", default="11:00:00"),
        f("column_break_c", "Column Break"),
        f("gstin", "Data", label="GSTIN"),
        f("disabled", "Check"),
    ], autoname="field:property_name", naming_rule="By fieldname")

    # ── Room Type ────────────────────────────────────────────────────────
    _dt("Room Type", [
        f("property", "Link", options="Property", reqd=1),
        f("room_type_code", "Data", reqd=1,
          description="Short unique code per property, e.g. DELUXE"),
        f("column_break_a", "Column Break"),
        f("room_type_name", "Data", reqd=1, in_list_view=1),
        f("description", "Small Text"),
        f("sb_pricing", "Section Break", label="Occupancy-based Pricing"),
        f("base_price", "Currency", reqd=1, in_list_view=1,
          description="Nightly rate including base_occupancy adults"),
        f("base_occupancy", "Int", default="2",
          description="Adults included in base price"),
        f("single_occupancy_price", "Currency",
          description="Blank = use base price"),
        f("column_break_p", "Column Break"),
        f("extra_adult_price", "Currency",
          description="Per night, per adult beyond base occupancy"),
        f("extra_bed_price", "Currency"),
        f("max_extra_beds", "Int", default="0"),
        f("sb_children", "Section Break", label="Children Policy"),
        f("free_child_age", "Int", default="5",
          description="Children at/under this age stay free"),
        f("child_age_limit", "Int", default="11",
          description="Children above this age are charged as adults"),
        f("column_break_ch", "Column Break"),
        f("child_price", "Currency",
          description="Per night, per child between free age and age limit"),
        f("tax_percent", "Percent", label="GST %", default="5"),
        f("sb_capacity", "Section Break", label="Capacity & Attributes"),
        f("adults_capacity", "Int", default="2"),
        f("children_capacity", "Int", default="1"),
        f("max_total_occupants", "Int"),
        f("bed_type", "Select", options="\nKing\nQueen\nTwin\nDouble\nSingle"),
        f("column_break_at", "Column Break"),
        f("room_view", "Data", label="View"),
        f("smoking_allowed", "Check"),
        f("amenities", "Small Text",
          description="Comma-separated, e.g. WiFi, AC, TV"),
        f("image", "Attach Image"),
        f("disabled", "Check"),
    ], autoname="format:{property}-{room_type_code}",
       naming_rule="Expression", title_field="room_type_name")

    # ── Room ─────────────────────────────────────────────────────────────
    _dt("Room", [
        f("property", "Link", options="Property", reqd=1),
        f("room_number", "Data", reqd=1, in_list_view=1),
        f("room_type", "Link", options="Room Type", reqd=1, in_list_view=1),
        f("column_break_a", "Column Break"),
        f("floor", "Data"),
        f("housekeeping_status", "Select", in_list_view=1, in_standard_filter=1,
          options="Clean\nDirty\nInspected\nOut of Order", default="Clean"),
        f("occupancy_status", "Select", in_list_view=1, read_only=1,
          options="Vacant\nOccupied", default="Vacant"),
        f("notes", "Small Text"),
    ], autoname="format:{property}-{room_number}", naming_rule="Expression",
       title_field="room_number")

    # ── Rate Plan ────────────────────────────────────────────────────────
    _dt("Rate Plan", [
        f("property", "Link", options="Property", reqd=1),
        f("rate_plan_name", "Data", reqd=1, in_list_view=1),
        f("code", "Data"),
        f("column_break_a", "Column Break"),
        f("modifier_type", "Select",
          options="Percent\nAmount\nAbsolute", default="Percent",
          description="How this plan adjusts the occupancy-computed room total"),
        f("modifier_value", "Float",
          description="-10 = 10% off; 0 = base rate (BAR)"),
        f("cancellation_policy", "Small Text"),
        f("is_default", "Check"),
        f("disabled", "Check"),
    ], autoname="format:{property}-{code}", naming_rule="Expression",
       title_field="rate_plan_name")

    # ── Guest ────────────────────────────────────────────────────────────
    _dt("Guest", [
        f("first_name", "Data", reqd=1),
        f("last_name", "Data"),
        f("full_name", "Data", read_only=1, in_list_view=1),
        f("column_break_a", "Column Break"),
        f("phone", "Data", options="Phone", in_list_view=1,
          in_standard_filter=1),
        f("email", "Data", options="Email"),
        f("vip", "Check", label="VIP", in_list_view=1),
        f("sb_id", "Section Break", label="Identity"),
        f("id_type", "Select",
          options="\nAadhaar\nPassport\nDriving License\nVoter ID\nOther"),
        f("id_number", "Data"),
        f("column_break_b", "Column Break"),
        f("nationality", "Data", default="Indian"),
        f("guest_notes", "Small Text",
          description="Preferences, allergies, history notes"),
    ], naming_rule="Expression", autoname="format:G-{#####}",
       title_field="full_name")

    # ── Reservation ──────────────────────────────────────────────────────
    _dt("Reservation", [
        f("property", "Link", options="Property", reqd=1),
        f("guest", "Link", options="Guest", reqd=1),
        f("guest_name", "Data", fetch_from="guest.full_name", read_only=1,
          in_list_view=1),
        f("column_break_a", "Column Break"),
        f("status", "Select", in_list_view=1, in_standard_filter=1,
          options="Confirmed\nChecked In\nChecked Out\nCancelled\nNo Show",
          default="Confirmed"),
        f("source", "Select",
          options="Manual\nAI Agent\nPhone\nWalk-in\nOTA\nWebsite",
          default="Manual"),
        f("channel", "Data",
          description="OTA name for channel bookings, e.g. booking.com"),
        f("sb_stay", "Section Break", label="Stay"),
        f("room_type", "Link", options="Room Type", reqd=1),
        f("room", "Link", options="Room"),
        f("column_break_b", "Column Break"),
        f("check_in_date", "Date", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("check_out_date", "Date", reqd=1, in_list_view=1),
        f("nights", "Int", read_only=1),
        f("column_break_c", "Column Break"),
        f("adults", "Int", default="2"),
        f("children", "Int", default="0"),
        f("sb_actual", "Section Break", label="Actuals"),
        f("actual_check_in", "Datetime", read_only=1),
        f("column_break_d", "Column Break"),
        f("actual_check_out", "Datetime", read_only=1),
        f("sb_money", "Section Break", label="Money"),
        f("amount_before_tax", "Currency"),
        f("tax_amount", "Currency"),
        f("column_break_e", "Column Break"),
        f("amount_after_tax", "Currency"),
        f("advance_paid", "Currency"),
        f("is_pay_at_hotel", "Check", label="Pay at Hotel"),
        f("sb_notes", "Section Break", label="Notes"),
        f("special_requests", "Small Text"),
    ], naming_rule="Expression", autoname="format:RES-{YYYY}-{#####}",
       title_field="guest_name")

    # ── Housekeeping Task ────────────────────────────────────────────────
    _dt("Housekeeping Task", [
        f("property", "Link", options="Property", reqd=1),
        f("room", "Link", options="Room", reqd=1, in_list_view=1),
        f("task_type", "Select", in_list_view=1,
          options="Checkout Clean\nStayover Clean\nDeep Clean\nInspection\nMaintenance",
          default="Checkout Clean"),
        f("column_break_a", "Column Break"),
        f("priority", "Select", options="Low\nMedium\nHigh\nUrgent",
          default="Medium", in_list_view=1),
        f("status", "Select", in_list_view=1, in_standard_filter=1,
          options="Pending\nIn Progress\nDone\nVerified", default="Pending"),
        f("assigned_to_user", "Link", options="User", label="Assigned To"),
        f("due_by", "Datetime"),
        f("notes", "Small Text"),
        f("reservation", "Link", options="Reservation",
          description="Set when auto-created by a checkout"),
    ], naming_rule="Expression", autoname="format:HK-{#####}")

    # ── Agent Action Log (the savings ledger) ────────────────────────────
    _dt("Agent Action Log", [
        f("agent_name", "Data", reqd=1, in_list_view=1,
          description='Which agent (or "human") performed the action'),
        f("action_type", "Data", reqd=1, in_list_view=1),
        f("column_break_a", "Column Break"),
        f("autonomy", "Select", options="Full\nSuggest\nApproved",
          default="Full"),
        f("action_channel", "Select",
          options="\nDesk\nVoice\nWhatsApp\nAPI", label="Channel"),
        f("sb_ref", "Section Break", label="Reference"),
        f("reference_doctype", "Link", options="DocType"),
        f("reference_name", "Dynamic Link", options="reference_doctype"),
        f("column_break_b", "Column Break"),
        f("property", "Link", options="Property"),
        f("minutes_saved", "Float", in_list_view=1,
          description="Estimated staff minutes avoided by this action"),
        f("sb_why", "Section Break", label="Explainability"),
        f("rationale", "Small Text",
          description="Human-readable reason the agent took this action"),
    ], naming_rule="Expression", autoname="format:AAL-{YYYY}-{######}",
       extra={"in_create": 0})

    frappe.db.commit()
    print("Kamra v0 schema bootstrapped.")
