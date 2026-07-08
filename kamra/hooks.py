app_name = "kamra"
app_title = "Kamra"
app_publisher = "HeyKoala"
app_description = (
	"Open-source, AI-native hotel PMS — front desk, direct booking, "
	"housekeeping, folios and GST billing, with an MCP tool layer so AI "
	"agents can run the property."
)
app_email = "hello@kamrapms.com"
app_license = "agpl-3.0"

# Branding shown in the Desk navbar, app switcher and marketplace listing.
app_logo_url = "/assets/kamra/kamra-mark.svg"
app_icon = "octicon octicon-home"
app_color = "#1E7B4F"

# The product UI is the React SPA at /kamra; surface it in the Apps launcher
# (and the /apps grid) so users land on it instead of the Desk.
add_to_apps_screen = [
	{
		"name": "kamra",
		"logo": "/assets/kamra/kamra-mark.svg",
		"title": "Kamra",
		"route": "/kamra",
	}
]

# Automated end-of-day: post room charges, flag no-shows, per property.
scheduler_events = {
	"cron": {
		# 03:00 site time, daily
		"0 3 * * *": ["kamra.folio.nightly_audit_all_properties"],
		# 03:30 - ORION pre-assigns tomorrow's arrivals (after the night audit)
		"30 3 * * *": ["kamra.allocation.run_nightly_allocation"],
	},
	"hourly": [
		# Expire Pending Agent Actions past their TTL so they don't linger in the
		# Inbox forever (default TTL is 72h; set on Pending Agent Action.before_insert).
		"kamra.autonomy.expire_stale_pending",
	],
}

# Apps
# ------------------

required_apps = ["payments"]

# Localization packs by country (regional_overrides style). A future
# kamra_uae APP declares its own to claim "United Arab Emirates".
kamra_localization = {
	"India": "kamra.localization.india",
}

# Served single-page app
# -----------------------
# The React front-end mounts at /kamra and owns all client-side routes
# (front desk, booking engine, housekeeping, self check-in). The `kamra` www
# page (kamra/www/kamra.py) serves the built shell with the CSRF token
# injected; every deep link falls through to it so browser refresh works.
website_route_rules = [
	{"from_route": "/kamra/<path:app_path>", "to_route": "kamra"},
]

# Clean, shareable guest URLs redirect into the SPA's routes.
website_redirects = [
	{"source": r"/book$", "target": "/kamra/book"},
	{"source": r"/book/(.*)", "target": r"/kamra/book/\1"},
	{"source": r"/hk$", "target": "/kamra/hk"},
	{"source": r"/checkin/(.*)", "target": r"/kamra/checkin/\1"},
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "kamra",
# 		"logo": "/assets/kamra/logo.png",
# 		"title": "Kamra",
# 		"route": "/kamra",
# 		"has_permission": "kamra.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/kamra/css/kamra.css"
# app_include_js = "/assets/kamra/js/kamra.js"

# include js, css files in header of web template
# web_include_css = "/assets/kamra/css/kamra.css"
# web_include_js = "/assets/kamra/js/kamra.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "kamra/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "kamra/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "kamra.utils.jinja_methods",
# 	"filters": "kamra.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "kamra.install.before_install"
# after_install = "kamra.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "kamra.uninstall.before_uninstall"
# after_uninstall = "kamra.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "kamra.utils.before_app_install"
# after_app_install = "kamra.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "kamra.utils.before_app_uninstall"
# after_app_uninstall = "kamra.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "kamra.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "kamra.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	doctype: {
		"on_update": "kamra.realtime.notify",
		"after_insert": "kamra.realtime.notify",
		"on_trash": "kamra.realtime.notify",
	}
	for doctype in ("Reservation", "Folio", "Room", "Housekeeping Task",
	                "Venue Booking", "Group Booking")
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"kamra.tasks.all"
# 	],
# 	"daily": [
# 		"kamra.tasks.daily"
# 	],
# 	"hourly": [
# 		"kamra.tasks.hourly"
# 	],
# 	"weekly": [
# 		"kamra.tasks.weekly"
# 	],
# 	"monthly": [
# 		"kamra.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "kamra.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "kamra.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "kamra.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "kamra.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["kamra.utils.before_request"]
# after_request = ["kamra.utils.after_request"]

# Job Events
# ----------
# before_job = ["kamra.utils.before_job"]
# after_job = ["kamra.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"kamra.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

