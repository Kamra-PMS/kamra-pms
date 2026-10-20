"""Unit tests for the GHCR retention planner (no network).

Run: python -m unittest discover -s .github/scripts -p 'test_*.py'
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ghcr_retention import PlanError, Version, plan_retention, select_keep_tags


def tagged(id_, tags, kids=()):
	"""An index version plus its untagged child versions (image + attestation)."""
	idx = Version(id=id_, digest=f"sha256:idx{id_}", tags=tuple(tags))
	children = [
		Version(id=id_ * 10 + i, digest=f"sha256:kid{id_}-{i}", tags=()) for i in range(len(kids) or 2)
	]
	return idx, children


class Registry:
	def __init__(self):
		self.refs = {}
		self.calls = []

	def add(self, idx, children):
		self.refs[idx.digest] = [c.digest for c in children]
		for c in children:
			self.refs.setdefault(c.digest, [])

	def children(self, digest):
		self.calls.append(digest)
		return self.refs.get(digest, [])


def build(*specs):
	reg = Registry()
	versions = []
	for id_, tags in specs:
		idx, kids = tagged(id_, tags)
		reg.add(idx, kids)
		versions += [idx, *kids]
	return versions, reg


class SelectKeepTags(unittest.TestCase):
	def test_semver_not_lexical(self):
		tags = ["v2.6.9", "v2.6.10", "v2.6.16", "v2.6.2", "latest", "nightly", "v2.7.0-rc.1"]
		self.assertEqual(select_keep_tags(tags, 3), ["latest", "nightly", "v2.6.16", "v2.6.10", "v2.6.9"])

	def test_floating_order_and_stable(self):
		self.assertEqual(
			select_keep_tags(["nightly", "stable", "latest"], 3), ["latest", "stable", "nightly"]
		)


class PlanRetention(unittest.TestCase):
	def test_current_registry_shape_keeps_everything(self):
		versions, reg = build(
			(1, ["v2.6.16", "latest"]),
			(2, ["nightly"]),
			(3, ["v2.6.15"]),
			(4, ["v2.6.14"]),
		)
		plan = plan_retention(versions, reg.children)
		self.assertEqual(plan.delete, [])
		self.assertEqual(len(plan.keep), 12)
		self.assertIn("floating tag 'stable' not found (nothing to keep for it)", plan.warnings)

	def test_old_release_and_its_children_deleted_children_of_kept_kept(self):
		versions, reg = build(
			(1, ["v2.6.17", "latest", "stable"]),
			(2, ["nightly"]),
			(3, ["v2.6.16"]),
			(4, ["v2.6.15"]),
			(5, ["v2.6.14"]),
			(6, ["buildcache"]),
		)
		stray = Version(id=999, digest="sha256:orphan", tags=())
		plan = plan_retention([*versions, stray], reg.children)
		deleted = {v.id for v in plan.delete}
		self.assertEqual(deleted, {5, 50, 51, 6, 60, 61, 999})
		kept = {v.id for v in plan.keep}
		for i in (1, 2, 3, 4):
			self.assertTrue({i, i * 10, i * 10 + 1} <= kept)

	def test_shared_child_digest_is_kept(self):
		versions, reg = build((1, ["v1.0.1"]), (2, ["v0.9.0"]))
		# v0.9.0 (deleted with keep_releases=1) shares a child with v1.0.1
		reg.refs["sha256:idx2"] = ["sha256:kid1-0", "sha256:kid2-1"]
		plan = plan_retention(versions, reg.children, keep_releases=1)
		deleted = {v.digest for v in plan.delete}
		self.assertNotIn("sha256:kid1-0", deleted)
		self.assertEqual(deleted, {"sha256:idx2", "sha256:kid2-0", "sha256:kid2-1"})

	def test_nested_index_resolved_recursively(self):
		versions, reg = build((1, ["latest"]))
		grandchild = Version(id=7, digest="sha256:grand", tags=())
		reg.refs["sha256:kid1-0"] = ["sha256:grand"]
		plan = plan_retention([*versions, grandchild], reg.children)
		self.assertEqual(plan.delete, [])

	def test_children_only_fetched_for_kept(self):
		versions, reg = build((1, ["latest"]), (2, ["old"]))
		plan_retention(versions, reg.children)
		self.assertNotIn("sha256:idx2", reg.calls)

	def test_empty_keep_set_aborts(self):
		versions, reg = build((1, ["foo"]), (2, ["bar"]))
		with self.assertRaises(PlanError):
			plan_retention(versions, reg.children)

	def test_no_versions_aborts(self):
		with self.assertRaises(PlanError):
			plan_retention([], lambda d: [])

	def test_registry_failure_aborts(self):
		versions, _ = build((1, ["latest"]))

		def boom(_d):
			raise RuntimeError("HTTP 500")

		with self.assertRaises(RuntimeError):
			plan_retention(versions, boom)

	def test_keep_releases_zero_keeps_only_floating(self):
		versions, reg = build((1, ["latest"]), (2, ["v1.0.0"]))
		plan = plan_retention(versions, reg.children, keep_releases=0)
		self.assertEqual({v.id for v in plan.delete}, {2, 20, 21})


if __name__ == "__main__":
	unittest.main()
