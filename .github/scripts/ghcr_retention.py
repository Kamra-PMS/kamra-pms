#!/usr/bin/env python3
"""Prune old ghcr.io/kamra-pms/kamra package versions — safely.

Keeps the floating tags (``latest``, ``stable``, ``nightly``), the N most
recent ``vX.Y.Z`` release tags (default 3), and **every manifest those tags
reference**. Each tag is an OCI image index whose children (the amd64 image
and its build attestation) show up in GitHub Packages as separate, untagged
versions; deleting "untagged" versions blindly breaks the tagged images, so
children are resolved through the registry API (recursively) and kept.
Every other version is deleted.

Dry run by default; ``--apply`` deletes. Aborts (exit 2) when the keep set
is empty or the plan would delete a version carrying a kept tag. Before
deleting, the plan is recomputed and only versions both plans agree on are
deleted (a release or nightly published mid-run is never touched).

Standard library only, so it runs on a bare ``ubuntu-latest`` Python.

Usage::

    GH_TOKEN=... python .github/scripts/ghcr_retention.py --org Kamra-PMS --package kamra
    GH_TOKEN=... python .github/scripts/ghcr_retention.py --org Kamra-PMS --package kamra --apply
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

FLOATING_TAGS = ("latest", "stable", "nightly")
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
MANIFEST_ACCEPT = ", ".join(
	(
		"application/vnd.oci.image.index.v1+json",
		"application/vnd.docker.distribution.manifest.list.v2+json",
		"application/vnd.oci.image.manifest.v1+json",
		"application/vnd.docker.distribution.manifest.v2+json",
	)
)
API = "https://api.github.com"
REGISTRY = "https://ghcr.io"


class PlanError(Exception):
	"""The plan is unsafe; nothing may be deleted."""


@dataclass(frozen=True)
class Version:
	id: int
	digest: str
	tags: tuple[str, ...]
	created_at: str = ""


@dataclass
class Plan:
	keep_tags: list[str]
	keep: list[Version]
	delete: list[Version]
	warnings: list[str] = field(default_factory=list)


def release_key(tag: str) -> tuple[int, int, int]:
	m = RELEASE_TAG.match(tag)
	assert m, tag
	return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def select_keep_tags(tags: Iterable[str], keep_releases: int = 3) -> list[str]:
	"""Floating tags present + the ``keep_releases`` highest vX.Y.Z tags (by SemVer, not date)."""
	tags = set(tags)
	floating = [t for t in FLOATING_TAGS if t in tags]
	releases = sorted((t for t in tags if RELEASE_TAG.match(t)), key=release_key, reverse=True)
	return floating + releases[: max(keep_releases, 0)]


def plan_retention(
	versions: list[Version],
	children: Callable[[str], list[str]],
	keep_releases: int = 3,
) -> Plan:
	"""Decide what to keep and delete.

	``children(digest)`` returns the digests a manifest references (an image
	index's ``manifests[]``; [] for a plain image manifest). It is only called
	for kept digests, and any exception it raises aborts the plan.
	"""
	all_tags = [t for v in versions for t in v.tags]
	keep_tags = select_keep_tags(all_tags, keep_releases)
	warnings: list[str] = []
	for t in FLOATING_TAGS:
		if t not in all_tags:
			warnings.append(f"floating tag '{t}' not found (nothing to keep for it)")
	if not keep_tags:
		raise PlanError("keep set is empty — refusing to delete anything")

	roots = {v.digest for v in versions if set(v.tags) & set(keep_tags)}
	keep_digests: set[str] = set()
	queue = sorted(roots)
	while queue:
		digest = queue.pop()
		if digest in keep_digests:
			continue
		keep_digests.add(digest)
		queue.extend(c for c in children(digest) if c not in keep_digests)

	known = {v.digest for v in versions}
	for d in sorted(keep_digests - known):
		warnings.append(f"kept manifest {d} is referenced but not listed as a package version")

	keep = [v for v in versions if v.digest in keep_digests]
	delete = [v for v in versions if v.digest not in keep_digests]

	# Belt and braces: the construction above already guarantees these.
	if not keep:
		raise PlanError("keep set resolved to no package versions — refusing to delete anything")
	for v in delete:
		hit = set(v.tags) & set(keep_tags)
		if hit:
			raise PlanError(f"plan would delete version {v.id} carrying kept tag(s) {sorted(hit)}")
	return Plan(keep_tags=keep_tags, keep=keep, delete=delete, warnings=warnings)


# --- HTTP ---------------------------------------------------------------------


def _request(url: str, headers: dict[str, str], method: str = "GET") -> tuple[int, dict, bytes]:
	req = urllib.request.Request(url, headers=headers, method=method)
	try:
		with urllib.request.urlopen(req, timeout=60) as resp:
			return resp.status, dict(resp.headers), resp.read()
	except urllib.error.HTTPError as e:
		return e.code, dict(e.headers or {}), e.read()


class GitHubPackages:
	def __init__(self, token: str, owner: str, package: str, owner_type: str = "org"):
		self.token = token
		self.package = package
		base = "orgs" if owner_type == "org" else "users"
		self.base = f"{API}/{base}/{owner}/packages/container/{urllib.parse.quote(package, safe='')}"
		self.headers = {
			"Authorization": f"Bearer {token}",
			"Accept": "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28",
			"User-Agent": "kamra-ghcr-retention",
		}

	def versions(self) -> list[Version]:
		out: list[Version] = []
		page = 1
		while True:
			status, _, body = _request(f"{self.base}/versions?per_page=100&page={page}", self.headers)
			if status != 200:
				raise RuntimeError(f"listing versions failed: HTTP {status} {body[:300]!r}")
			rows = json.loads(body)
			for r in rows:
				tags = tuple((r.get("metadata") or {}).get("container", {}).get("tags") or ())
				out.append(
					Version(id=int(r["id"]), digest=r["name"], tags=tags, created_at=r.get("created_at", ""))
				)
			if len(rows) < 100:
				return out
			page += 1

	def delete(self, version_id: int) -> tuple[int, str]:
		status, _, body = _request(f"{self.base}/versions/{version_id}", self.headers, method="DELETE")
		return status, body[:300].decode("utf-8", "replace")


class Registry:
	def __init__(self, image: str, username: str, token: str):
		self.image = image  # e.g. kamra-pms/kamra (lowercase)
		basic = base64.b64encode(f"{username}:{token}".encode()).decode()
		scope = urllib.parse.quote(f"repository:{image}:pull", safe="")
		status, _, body = _request(
			f"{REGISTRY}/token?service=ghcr.io&scope={scope}",
			{"Authorization": f"Basic {basic}", "User-Agent": "kamra-ghcr-retention"},
		)
		if status != 200:
			raise RuntimeError(f"registry token failed: HTTP {status} {body[:200]!r}")
		self.bearer = json.loads(body)["token"]
		self._cache: dict[str, list[str]] = {}

	def children(self, digest: str) -> list[str]:
		if digest in self._cache:
			return self._cache[digest]
		status, _, body = _request(
			f"{REGISTRY}/v2/{self.image}/manifests/{digest}",
			{
				"Authorization": f"Bearer {self.bearer}",
				"Accept": MANIFEST_ACCEPT,
				"User-Agent": "kamra-ghcr-retention",
			},
		)
		if status != 200:
			raise RuntimeError(f"manifest {digest}: HTTP {status} {body[:200]!r}")
		doc = json.loads(body)
		kids = [m["digest"] for m in doc.get("manifests") or []]
		self._cache[digest] = kids
		return kids


# --- CLI ----------------------------------------------------------------------


def describe(v: Version) -> str:
	tags = ",".join(v.tags) or "(untagged)"
	return f"{v.id:>12}  {v.digest[:19]}…  {v.created_at[:10]}  {tags}"


def render(plan: Plan, apply: bool) -> str:
	lines = [
		f"Mode: {'APPLY (deleting)' if apply else 'dry run (nothing deleted)'}",
		f"Kept tags: {', '.join(plan.keep_tags)}",
		"",
		f"KEEP ({len(plan.keep)}):",
		*(f"  {describe(v)}" for v in plan.keep),
		"",
		f"DELETE ({len(plan.delete)}):",
		*(f"  {describe(v)}" for v in plan.delete),
	]
	if plan.warnings:
		lines += ["", "Warnings:", *(f"  - {w}" for w in plan.warnings)]
	return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
	p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	p.add_argument("--org", required=True, help="package owner (org or user)")
	p.add_argument("--owner-type", choices=("org", "user"), default="org")
	p.add_argument("--package", required=True)
	p.add_argument("--keep-releases", type=int, default=3)
	p.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
	args = p.parse_args(argv)

	token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
	if not token:
		print("GH_TOKEN is not set", file=sys.stderr)
		return 2
	username = os.environ.get("REGISTRY_USER") or os.environ.get("GITHUB_ACTOR") or "token"

	gh = GitHubPackages(token, args.org, args.package, args.owner_type)
	registry = Registry(f"{args.org.lower()}/{args.package.lower()}", username, token)

	try:
		plan = plan_retention(gh.versions(), registry.children, args.keep_releases)
	except PlanError as e:
		print(f"ABORT: {e}", file=sys.stderr)
		return 2

	report = render(plan, args.apply)
	print(report)
	summary = os.environ.get("GITHUB_STEP_SUMMARY")
	if summary:
		with open(summary, "a", encoding="utf-8") as fh:
			fh.write(f"## GHCR retention — {args.package}\n\n```\n{report}\n```\n")

	if not args.apply or not plan.delete:
		return 0

	# Re-plan right before deleting; only delete what both plans agree on.
	try:
		again = plan_retention(gh.versions(), registry.children, args.keep_releases)
	except PlanError as e:
		print(f"ABORT on re-plan: {e}", file=sys.stderr)
		return 2
	agreed = {v.id for v in again.delete}
	failures = 0
	for v in plan.delete:
		if v.id not in agreed:
			print(f"skip {v.id}: no longer in the delete plan")
			continue
		status, body = gh.delete(v.id)
		if status in (200, 204):
			print(f"deleted {describe(v)}")
		else:
			failures += 1
			hint = ""
			if status in (401, 403):
				hint = (
					" (token lacks delete rights: give this repo the Admin role under package"
					" settings → Manage Actions access, or set the GHCR_RETENTION_TOKEN secret)"
				)
			print(f"FAILED {v.id}: HTTP {status} {body}{hint}", file=sys.stderr)
	return 1 if failures else 0


if __name__ == "__main__":
	sys.exit(main())
