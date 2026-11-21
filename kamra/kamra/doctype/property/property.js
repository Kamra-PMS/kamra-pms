// Copyright (c) 2026, HeyKoala and contributors
// For license information, please see license.txt

frappe.ui.form.on("Property", {
	refresh(frm) {
		if (!frm.fields_dict.booking_language) return
		frappe.call({
			method: "kamra.languages.enabled_ui_languages",
			callback(r) {
				const enabled = (r.message && r.message.enabled) || ["en"]
				const current = frm.doc.booking_language
				const codes = enabled.includes(current) || !current ? enabled : [current, ...enabled]
				frm.set_df_property("booking_language", "fieldtype", "Select")
				frm.set_df_property("booking_language", "options", ["", ...codes].join("\n"))
				frm.refresh_field("booking_language")
			},
		})
	},
})
