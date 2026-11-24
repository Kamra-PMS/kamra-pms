"""Regenerate the permission tables in roles-and-access.md from the code:
every @require_perm(doctype, ptype) endpoint and each doctype's DocPerm.
Run from docs-site/:  python3 gen_permissions.py"""

import ast
import json
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = pathlib.Path(__file__).with_name("roles-and-access.md")
START, END = "<!-- permissions:start -->", "<!-- permissions:end -->"
STD = ("read", "write", "create", "delete", "report", "export")


def doctype_json(name):
	slug = name.replace(" ", "_").lower()
	return json.loads((ROOT / "kamra/kamra/doctype" / slug / f"{slug}.json").read_text())


def main():
	actions = defaultdict(list)  # (doctype, ptype) -> endpoints
	for path in sorted((ROOT / "kamra").rglob("*.py")):
		if any(p in path.parts for p in ("tests", "patches", "scripts")):
			continue
		for node in ast.walk(ast.parse(path.read_text())):
			if isinstance(node, ast.FunctionDef):
				for d in node.decorator_list:
					if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "require_perm":
						dt, pt = (ast.literal_eval(a) for a in d.args[:2])
						mod = ".".join(path.relative_to(ROOT / "kamra").with_suffix("").parts)
						actions[(dt, pt)].append(f"{mod}.{node.name}")
	ptypes = {(j["doc_type"], j["perm_type"]) for j in (
		json.loads(p.read_text()) for p in (ROOT / "kamra/kamra/permission_type").glob("*/*.json"))}
	out = ["| Doctype | Permission | Default roles | Endpoints |", "| --- | --- | --- | --- |"]
	for dt, pt in sorted(ptypes):
		roles = [p["role"] for p in doctype_json(dt)["permissions"]
		         if p.get(pt) and not p.get("permlevel")]
		eps = actions.get((dt, pt), [])
		shown = ", ".join(f"`{e}`" for e in eps[:3]) + (f" and {len(eps) - 3} more" if len(eps) > 3 else "")
		label = pt.replace("_", " ").capitalize()
		out.append(f"| {dt} | {label} (`{pt}`) | {', '.join(sorted(roles))} | {shown or 'checked inside Kamra'} |")
	out += ["", "Record access over Desk and REST (standard rights, permission level 0):", "",
	        "| Doctype | Role | Rights |", "| --- | --- | --- |"]
	for path in sorted((ROOT / "kamra/kamra/doctype").glob("*/*.json")):
		j = json.loads(path.read_text())
		if j.get("doctype") != "DocType" or j.get("istable") or j.get("module") != "Kamra":
			continue
		for p in j.get("permissions", []):
			rights = [r for r in STD if p.get(r)]
			if rights and not p.get("permlevel"):
				out.append(f"| {j['name']} | {p['role']} | {', '.join(rights)} |")
	text = PAGE.read_text()
	head, rest = text.split(START, 1)
	PAGE.write_text(head + START + "\n" + "\n".join(out) + "\n" + END + rest.split(END, 1)[1])
	print(f"wrote {len(ptypes)} permission types to {PAGE.name}")


if __name__ == "__main__":
	main()
