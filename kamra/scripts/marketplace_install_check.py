# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Offline marketplace-install simulation.

Mirrors the checks Frappe Cloud and CI run before a site can serve Kamra:
pyproject, hooks, license, prebuilt SPA, route rules, and no leftover
Semgrep-blocking `frappe.set_user` / `frappe.db.commit` without nosemgrep.

Does not need MariaDB. The full bench path (get-app + install-app + evals)
runs in `.github/workflows/ci.yml` on every push to main.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "kamra"


def fail(msg: str) -> None:
	print(f"FAIL  {msg}")
	raise SystemExit(1)


def ok(msg: str) -> None:
	print(f"PASS  {msg}")


def check_pyproject() -> None:
	data = tomllib.loads((ROOT / "pyproject.toml").read_text())
	project = data["project"]
	if project.get("name") != "kamra":
		fail("pyproject name is not kamra")
	req = project.get("requires-python", "")
	if not req.startswith(">=") or "3.10" not in req:
		fail(f"requires-python floor too high for FC v16: {req!r}")
	deps = data.get("tool", {}).get("bench", {}).get("frappe-dependencies", {})
	frappe_spec = deps.get("frappe", "")
	if "16" not in frappe_spec or "<17" not in frappe_spec:
		fail(f"bad frappe version specifier: {frappe_spec!r}")
	ok(f"pyproject.toml valid (python {req}, frappe {frappe_spec})")


def check_hooks() -> None:
	src = (APP / "hooks.py").read_text()
	tree = ast.parse(src)
	ns: dict[str, object] = {}
	for node in tree.body:
		if isinstance(node, ast.Assign) and len(node.targets) == 1:
			name = getattr(node.targets[0], "id", None)
			if name in {
				"required_apps",
				"add_to_apps_screen",
				"website_route_rules",
				"app_name",
				"app_license",
			}:
				ns[name] = ast.literal_eval(node.value)
	if ns.get("app_name") != "kamra":
		fail("hooks.app_name is not kamra")
	if ns.get("required_apps") != ["payments"]:
		fail(f"required_apps expected ['payments'], got {ns.get('required_apps')}")
	screen = ns.get("add_to_apps_screen") or []
	if not screen or screen[0].get("route") != "/kamra":
		fail("add_to_apps_screen missing /kamra route")
	rules = str(ns.get("website_route_rules"))
	if "/kamra/<path:app_path>" not in rules:
		fail("/kamra SPA route rule missing")
	if ns.get("app_license") != "agpl-3.0":
		fail("app_license is not agpl-3.0")
	ok("hooks.py: payments, /kamra launcher, SPA route, AGPL")


def check_shipped_spa() -> None:
	index = APP / "public" / "frontend" / "index.html"
	boot = APP / "www" / "kamra.py"
	if not index.is_file():
		fail("prebuilt SPA missing at kamra/public/frontend/index.html")
	if not boot.is_file():
		fail("SPA boot page missing at kamra/www/kamra.py")
	html = index.read_text()
	if "/assets/kamra/frontend/assets/" not in html:
		fail("SPA index.html does not reference /assets/kamra/frontend/assets/")
	ok("prebuilt SPA shipped (marketplace benches do not run npm)")


def check_license_and_package() -> None:
	if not (ROOT / "license.txt").is_file() and not (ROOT / "LICENSE").is_file():
		fail("license.txt / LICENSE missing")
	pkg = (ROOT / "package.json").read_text()
	if '"build"' not in pkg:
		fail("root package.json missing build script (FC runs yarn build)")
	ok("license + FC yarn build entrypoint present")


def check_semgrep_same_line() -> None:
	"""FC auditor requires # nosemgrep on the same line as the call."""
	bad: list[str] = []
	for path in APP.rglob("*.py"):
		for i, line in enumerate(path.read_text().splitlines(), 1):
			stripped = line.lstrip()
			if stripped.startswith("#") or stripped.startswith(("\"\"\"", "'''")):
				continue
			if re.search(r"^\s*frappe\.set_user\(", line) and "nosemgrep: frappe-setuser" not in line:
				bad.append(f"{path.relative_to(ROOT)}:{i} set_user")
			if re.search(r"^\s*frappe\.db\.commit\(", line) and "nosemgrep: frappe-manual-commit" not in line:
				bad.append(f"{path.relative_to(ROOT)}:{i} commit")
	if bad:
		fail("unannotated dangerous calls:\n  " + "\n  ".join(bad))
	ok("every frappe.set_user / db.commit has same-line nosemgrep")


def check_listing_copy() -> None:
	md = (ROOT / "docs" / "marketplace-listing.md").read_text()
	# The paste-ready long description lives in a markdown fence.
	m = re.search(r"```markdown\n(.*?)```", md, re.S)
	if not m:
		fail("marketplace-listing.md missing paste-ready markdown fence")
	body = m.group(1)
	if re.search(r"https?://", body):
		fail("long description still contains URLs (FC metadata audit)")
	ok("listing long description has no extra URLs")


def main() -> None:
	print("Kamra marketplace install simulation (offline)\n")
	check_pyproject()
	check_hooks()
	check_shipped_spa()
	check_license_and_package()
	check_semgrep_same_line()
	check_listing_copy()
	print("\nMARKETPLACE-INSTALL CHECKS PASSED")
	print("Full bench path: GitHub Actions → Backend eval harness")
	print("  bench get-app payments && bench get-app kamra && install-app")


if __name__ == "__main__":
	sys.exit(main())
