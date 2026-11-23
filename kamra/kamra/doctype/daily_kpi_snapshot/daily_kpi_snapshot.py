# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class DailyKPISnapshot(Document):
	"""One business date's closing figures, written once by the night audit
	(kamra.reports.write_kpi_snapshot). Read it with kamra.reports.kpi_snapshots."""
