import json
import os
import re
from html import escape

import frappe
from frappe.utils import get_url, strip_html

# The SPA owns its own routing; never cache the boot shell.
no_cache = 1


def get_context(context):
	"""Serve the built React SPA shell with the session CSRF token injected.

	The front-end is built by Vite into kamra/public/frontend (served by Frappe
	at /assets/kamra/frontend/). We read that index.html at request time — so
	asset hashes never need to be hard-coded — and inject window.csrf_token so
	the SPA can POST to whitelisted endpoints once the user is logged in.
	"""
	index_path = frappe.get_app_path("kamra", "public", "frontend", "index.html")
	if not os.path.exists(index_path):
		frappe.throw(
			frappe._(
				"Kamra front-end is not built. Run "
				"<code>cd apps/kamra/frontend && yarn install && yarn build</code> "
				"(Frappe Cloud runs this automatically on deploy)."
			),
			title="Kamra not built",
		)

	with open(index_path, encoding="utf-8") as f:  # nosemgrep: frappe-security-file-traversal -- serves the app's own built index.html from a fixed app path, not user input
		html = f.read()

	csrf = frappe.sessions.get_csrf_token()
	# The socket.io namespace is the site name, which is not the hostname on
	# a custom domain - without it live updates silently never arrive.
	site = json.dumps(frappe.local.site).replace("<", "\\u003c")
	boot = f'<script>window.csrf_token = "{csrf}"; window.kamra_site = {site};</script>'
	# Inject before the module script so the token is set before the app boots.
	html = html.replace("</head>", boot + "</head>", 1)
	html = _with_meta(html, frappe.request.path if frappe.request else "/")

	context.spa_html = html
	context.no_cache = 1
	return context


# Link previews and most crawlers never run the SPA, so the guest pages get
# their title, description and image in the HTML itself. Staff screens and
# tokenized check-in links are kept out of search.
_GUEST = re.compile(r"^/(?:$|(?:kamra/)?book(?:/|$)|(?:kamra/)?stay/([^/]+))")


def _with_meta(html: str, path: str) -> str:
	match = _GUEST.match(path or "/")
	if not match:
		return html.replace("</head>", '<meta name="robots" content="noindex" /></head>', 1)
	meta = _guest_meta(match.group(1))
	if not meta:  # several hotels and none picked: the page lists them
		return html
	if meta.get("lang"):
		html = re.sub(r'<html lang="[^"]*"', f'<html lang="{escape(meta["lang"])}"', html, count=1)
	html = re.sub(r"<title>.*?</title>", f"<title>{escape(meta['title'])}</title>", html, count=1, flags=re.S)
	html = re.sub(r'<meta\s+name="description"[^>]*>', "", html, count=1, flags=re.S)
	tags = [
		f'<meta name="description" content="{escape(meta["description"])}" />',
		f'<meta property="og:title" content="{escape(meta["title"])}" />',
		f'<meta property="og:description" content="{escape(meta["description"])}" />',
		f'<meta property="og:url" content="{escape(get_url(path))}" />',
		'<meta property="og:type" content="website" />',
		f'<link rel="canonical" href="{escape(get_url(path))}" />',
	]
	if meta.get("image"):
		image = escape(get_url(meta["image"]) if meta["image"].startswith("/") else meta["image"])
		tags += [f'<meta property="og:image" content="{image}" />',
		         '<meta name="twitter:card" content="summary_large_image" />']

	head_tags = list(tags)
	body_tags = []

	gtm_id = meta.get("gtm_id")
	if gtm_id and re.match(r"^[A-Za-z0-9_-]+$", gtm_id):
		head_tags.append(
			"<!-- Google Tag Manager -->\n"
			"<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':\n"
			"new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],\n"
			"j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=\n"
			"'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);\n"
			f"}})(window,document,'script','dataLayer','{gtm_id}');</script>\n"
			"<!-- End Google Tag Manager -->"
		)
		body_tags.append(
			"<!-- Google Tag Manager (noscript) -->\n"
			f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"\n'
			'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>\n'
			"<!-- End Google Tag Manager (noscript) -->"
		)

	pixel_id = meta.get("meta_pixel_id")
	if pixel_id and re.match(r"^[0-9]+$", pixel_id):
		head_tags.append(
			"<!-- Meta Pixel Code -->\n"
			"<script>\n"
			"!function(f,b,e,v,n,t,s)\n"
			"{if(f.fbq)return;n=f.fbq=function(){n.callMethod?\n"
			"n.callMethod.apply(n,arguments):n.queue.push(arguments)};\n"
			"if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';\n"
			"n.queue=[];t=b.createElement(e);t.async=!0;\n"
			"t.src=v;s=b.getElementsByTagName(e)[0];\n"
			"s.parentNode.insertBefore(t,s)}(window, document,'script',\n"
			"'https://connect.facebook.net/en_US/fbevents.js');\n"
			f"fbq('init', '{pixel_id}');\n"
			"fbq('track', 'PageView');\n"
			"</script>\n"
			"<noscript><img height=\"1\" width=\"1\" style=\"display:none\"\n"
			f'src="https://www.facebook.com/tr?id={pixel_id}&ev=PageView&noscript=1"\n'
			"/></noscript>\n"
			"<!-- End Meta Pixel Code -->"
		)

	if meta.get("custom_header_script"):
		head_tags.append(meta["custom_header_script"])

	if meta.get("custom_body_script"):
		body_tags.append(meta["custom_body_script"])

	if body_tags:
		html = re.sub(r"(<body[^>]*>)", r"\1\n" + "\n".join(body_tags) + "\n", html, count=1, flags=re.IGNORECASE)

	return html.replace("</head>", "".join(head_tags) + "</head>", 1)


def _guest_meta(slug: str | None) -> dict | None:
	from kamra.booking_slugs import property_for_slug, resolve_public_slug

	listing = None
	try:
		if slug:
			scope = resolve_public_slug(slug)
			name = scope["property"]
			listing = scope.get("room_type_name")
		else:
			name = property_for_slug(frappe.form_dict.get("property") or "")
			if not name:
				live = frappe.get_all("Property", {"booking_engine_enabled": 1, "disabled": 0},
				                      pluck="name", limit=2)
				if len(live) != 1:
					return None
				name = live[0]
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return None
	prop = frappe.get_cached_doc("Property", name)
	place = ", ".join(x for x in (prop.city, prop.state) if x)
	title = prop.get("meta_title") or (
		f"{prop.property_name}{', ' + place if place else ''} · Book direct")
	if listing:
		title = f"{listing} · {prop.property_name}"
	description = (prop.get("meta_description")
	               or strip_html(prop.get("showcase_description") or "").strip()
	               or f"Book {prop.property_name}{' in ' + place if place else ''} directly with the hotel.")
	from kamra.languages import public_booking_language
	return {
		"title": title,
		"description": " ".join(description.split())[:160],
		"lang": public_booking_language(prop.get("booking_language")),
		"image": prop.get("og_image") or prop.get("hero_image") or prop.get("logo_url"),
		"gtm_id": (prop.get("google_tag_manager_id") or "").strip(),
		"meta_pixel_id": (prop.get("meta_pixel_id") or "").strip(),
		"custom_header_script": (prop.get("custom_header_script") or "").strip(),
		"custom_body_script": (prop.get("custom_body_script") or "").strip(),
	}
