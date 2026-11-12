"""Channel webhooks used to keep the guest's message text (WhatsApp) and the
call transcript (voice) in the Agent Action Log, for as long as the log.
Trim them to what new rows keep: the event and the provider's summary. Rows
past their property's message retention are then cleared as usual."""

import frappe


def execute():
	frappe.db.sql(
		"""UPDATE `tabAgent Action Log`
		SET rationale = 'WhatsApp inbound (message text removed)'
		WHERE action_type = 'whatsapp.inbound' AND rationale LIKE 'WhatsApp inbound: %%'""")
	# voice rows were "<summary>\n\n<transcript>": keep the summary, capped
	frappe.db.sql(
		"""UPDATE `tabAgent Action Log`
		SET rationale = LEFT(SUBSTRING_INDEX(rationale, '\n\n', 1), 280)
		WHERE action_type LIKE 'voice.%%'
		  AND (rationale LIKE '%%\n\n%%' OR CHAR_LENGTH(rationale) > 280)""")
	from kamra.privacy import apply_message_retention
	apply_message_retention()
