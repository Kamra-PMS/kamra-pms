"""Site health and version checks for self-hosted / cloud installs.

Read-only diagnostics for Admin → System Health. Upgrade is guided (bench /
Docker / Frappe Cloud) — we never mutate the install from this screen.
"""

from __future__ import annotations

import json
import re
import shutil
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import frappe
from frappe.utils import cint

from kamra import __version__ as KAMRA_VERSION
from kamra.authz import require_roles

GITHUB_REPO = "Kamra-PMS/kamra-pms"
GITHUB_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES = f"https://github.com/{GITHUB_REPO}/releases"
CACHE_KEY = "kamra:github_latest_release"
CACHE_TTL = 3600  # 1 hour — polite to GitHub's unauthenticated rate limit


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
	"""v2.6.2 / 2.6.2 → (2, 6, 2). Ignores prerelease suffixes for compare."""
	m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", (tag or "").strip())
	if not m:
		return None
	return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _cmp_semver(a: str, b: str) -> int | None:
	"""-1 if a < b, 0 equal, 1 if a > b, None if unparsable."""
	pa, pb = _parse_semver(a), _parse_semver(b)
	if not pa or not pb:
		return None
	if pa < pb:
		return -1
	if pa > pb:
		return 1
	return 0


def _fetch_github_latest() -> dict:
	cached = frappe.cache.get_value(CACHE_KEY)
	if isinstance(cached, dict) and cached.get("tag"):
		return cached

	req = Request(
		GITHUB_LATEST,
		headers={
			"Accept": "application/vnd.github+json",
			"User-Agent": f"Kamra-PMS/{KAMRA_VERSION}",
			"X-GitHub-Api-Version": "2022-11-28",
		},
	)
	try:
		with urlopen(req, timeout=8) as resp:  # nosemgrep: python.lang.security - public GitHub API over HTTPS
			payload = json.loads(resp.read().decode("utf-8"))
	except (HTTPError, URLError, TimeoutError, ValueError, OSError) as e:
		return {
			"ok": False,
			"error": str(e)[:200],
			"tag": None,
			"name": None,
			"url": GITHUB_RELEASES,
			"published_at": None,
		}

	tag = (payload.get("tag_name") or "").strip()
	out = {
		"ok": True,
		"error": None,
		"tag": tag,
		"name": payload.get("name") or tag,
		"url": payload.get("html_url") or GITHUB_RELEASES,
		"published_at": payload.get("published_at"),
		"body_preview": (payload.get("body") or "")[:400],
	}
	frappe.cache.set_value(CACHE_KEY, out, expires_in_sec=CACHE_TTL)
	return out


def _check(id_: str, title: str, status: str, detail: str, *,
           link: str | None = None) -> dict:
	"""status: passed | attention | failed | info"""
	return {
		"id": id_,
		"title": title,
		"status": status,
		"detail": detail,
		"link": link,
	}


def _disk_check() -> dict:
	try:
		usage = shutil.disk_usage(frappe.get_site_path())
		free_gb = usage.free / (1024 ** 3)
		total_gb = usage.total / (1024 ** 3)
		pct_free = (usage.free / usage.total) * 100 if usage.total else 0
		if free_gb < 2 or pct_free < 5:
			status = "failed"
		elif free_gb < 5 or pct_free < 10:
			status = "attention"
		else:
			status = "passed"
		return _check(
			"disk",
			"Disk space",
			status,
			f"{free_gb:.1f} GB free of {total_gb:.1f} GB ({pct_free:.0f}% free).",
		)
	except OSError as e:
		return _check("disk", "Disk space", "info", f"Could not measure: {e}")


def _scheduler_check() -> dict:
	enabled = cint(frappe.db.get_single_value("System Settings", "enable_scheduler"))
	if enabled:
		return _check(
			"scheduler",
			"Scheduler",
			"passed",
			"Background jobs are enabled (night audit, reminders, sync).",
		)
	return _check(
		"scheduler",
		"Scheduler",
		"attention",
		"Scheduler is off — night audit and reminder jobs will not run.",
		link="/app/system-settings",
	)


def _database_check() -> dict:
	try:
		frappe.db.sql("select 1")
		return _check("database", "Database", "passed", "Responding to queries.")
	except Exception as e:
		return _check("database", "Database", "failed", str(e)[:200])


def _frappe_check() -> dict:
	ver = getattr(frappe, "__version__", None) or "unknown"
	major = int(str(ver).split(".")[0]) if str(ver)[0:1].isdigit() else 0
	if major and major < 16:
		status = "attention"
		detail = f"Frappe {ver} — Kamra targets Frappe v16."
	else:
		status = "passed"
		detail = f"Frappe {ver}."
	return _check("frappe", "Frappe", status, detail)


def _apps_check() -> dict:
	apps = frappe.get_installed_apps()
	need = ["frappe", "kamra"]
	missing = [a for a in need if a not in apps]
	if missing:
		return _check(
			"apps",
			"Installed apps",
			"failed",
			f"Missing required app(s): {', '.join(missing)}. Installed: {', '.join(apps)}.",
		)
	optional = [a for a in ("payments", "erpnext", "hrms") if a in apps]
	extra = f" Optional: {', '.join(optional)}." if optional else ""
	return _check(
		"apps",
		"Installed apps",
		"passed",
		f"kamra + frappe present.{extra}",
	)


def _timezone_check() -> dict:
	site_tz = frappe.db.get_single_value("System Settings", "time_zone") or ""
	props = frappe.get_all("Property", fields=["name", "timezone"], limit=5)
	if not props:
		return _check(
			"timezone",
			"Time zone",
			"attention",
			f"Site clock is {site_tz or 'unset'}; no Property yet.",
		)
	mismatched = [
		p.name for p in props
		if (p.timezone or "").strip() and (p.timezone or "").strip() != site_tz
	]
	if mismatched and len(props) == 1:
		return _check(
			"timezone",
			"Time zone",
			"attention",
			f"Property timezone differs from site ({site_tz}). "
			"Set Time zone under Admin → Settings → Property.",
			link="/kamra/settings",
		)
	return _check(
		"timezone",
		"Time zone",
		"passed",
		f"Site clock: {site_tz or 'unset'}.",
	)


def _version_check(latest: dict) -> dict:
	installed = KAMRA_VERSION
	tag = latest.get("tag")
	url = latest.get("url") or GITHUB_RELEASES
	if not latest.get("ok") or not tag:
		return _check(
			"version",
			"Version",
			"info",
			f"Installed {installed}. Could not reach GitHub "
			f"({latest.get('error') or 'unknown'}).",
			link=url,
		)
	cmp = _cmp_semver(installed, tag)
	if cmp is None:
		return _check(
			"version",
			"Version",
			"info",
			f"Installed {installed}; latest on GitHub is {tag}.",
			link=url,
		)
	if cmp < 0:
		return _check(
			"version",
			"Version",
			"attention",
			f"Installed {installed} — latest stable is {tag.lstrip('v')}.",
			link=url,
		)
	if cmp > 0:
		return _check(
			"version",
			"Version",
			"info",
			f"Installed {installed} is ahead of latest GitHub release {tag} "
			"(develop / pre-release build).",
			link=url,
		)
	return _check(
		"version",
		"Version",
		"passed",
		f"Installed {installed} matches latest stable {tag}.",
		link=url,
	)


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager", "Administrator")
def system_health(refresh: int = 0):
	"""Admin diagnostics: version vs GitHub + site component checks."""
	if cint(refresh):
		frappe.cache.delete_value(CACHE_KEY)

	latest = _fetch_github_latest()
	checks = [
		_version_check(latest),
		_frappe_check(),
		_apps_check(),
		_database_check(),
		_scheduler_check(),
		_disk_check(),
		_timezone_check(),
	]

	summary = {
		"passed": sum(1 for c in checks if c["status"] == "passed"),
		"attention": sum(1 for c in checks if c["status"] == "attention"),
		"failed": sum(1 for c in checks if c["status"] == "failed"),
		"info": sum(1 for c in checks if c["status"] == "info"),
	}
	overall = "passed"
	if summary["failed"]:
		overall = "failed"
	elif summary["attention"]:
		overall = "attention"

	return {
		"overall": overall,
		"summary": summary,
		"installed": {
			"kamra": KAMRA_VERSION,
			"frappe": getattr(frappe, "__version__", None),
			"site": frappe.local.site,
		},
		"latest": latest,
		"upgrade": {
			"docs": "https://kamrapms.com/docs/self-hosting/",
			"releases": GITHUB_RELEASES,
			"docker_latest": "ghcr.io/kamra-pms/kamra:latest",
			"docker_nightly": "ghcr.io/kamra-pms/kamra:nightly",
			"bench": (
				"bench get-app kamra https://github.com/Kamra-PMS/kamra-pms "
				"--branch main && bench --site <site> migrate && bench build "
				"--app kamra && bench restart"
			),
			"note": (
				"Kamra does not auto-upgrade the site from this screen. "
				"Self-host: pull the new image or bench update, then migrate. "
				"Frappe Cloud: create a Marketplace release from main."
			),
		},
		"checks": checks,
	}
