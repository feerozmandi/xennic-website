#!/usr/bin/env python3
"""The automatic approval rule and the automatic version of a release.

These are the two decisions the host now makes on its own: whether a
migration transition is safe enough to approve without a person, and which
version the release that goes live carries. Both are checked here without a
host, a registry or a database: the rules are pure, and the parts that touch
the host are checked for the shape they refuse.
"""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

sys_dont = True
import sys  # noqa: E402

sys.dont_write_bytecode = True
p = Path(__file__).resolve().parents[1] / "scripts/preview-fixed-operations.py"
spec = importlib.util.spec_from_file_location("preview_fixed", p)
fixed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixed)


def entries(*names):
    """A migration tree as the archive reader returns it."""
    return [(name, f"// {name}\n".encode()) for name in names]


def compare(*messages):
    """The GitHub answer for the commits between two releases."""
    return {"status": "ahead", "ahead_by": len(messages),
            "commits": [{"commit": {"message": message}} for message in messages]}


class MigrationNameTest(unittest.TestCase):
    def test_the_declared_names_are_the_stems_of_the_migration_files(self):
        names = fixed.migration_names(entries(
            "app/migrations/index.ts", "app/migrations/20261030_163225_baseline.ts",
            "app/migrations/20261030_163225_baseline.json", "app/migrations/001-init.sql"))
        self.assertEqual(names, ["20261030_163225_baseline"])

    def test_a_tree_without_migration_files_declares_nothing(self):
        self.assertEqual(fixed.migration_names(entries("app/migrations/001-init.sql")), [])

    def test_an_unusable_name_is_refused(self):
        with self.assertRaises(fixed.Rejected):
            fixed.migration_names(entries("app/migrations/not a migration.ts"))


class MigrationDigestTest(unittest.TestCase):
    def test_the_same_tree_hashes_the_same_and_a_changed_tree_does_not(self):
        one = entries("app/migrations/index.ts", "app/migrations/a.ts")
        two = entries("app/migrations/index.ts", "app/migrations/a.ts")
        three = entries("app/migrations/index.ts", "app/migrations/b.ts")
        self.assertEqual(fixed.migration_digest(one), fixed.migration_digest(two))
        self.assertNotEqual(fixed.migration_digest(one), fixed.migration_digest(three))


class AutoApprovalSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "auto-approval.json"

    def write(self, data, mode=0o600):
        self.path.write_text(json.dumps(data))
        self.path.chmod(mode)

    def test_a_missing_file_means_off(self):
        with mock.patch.object(fixed, "AUTO_APPROVAL", self.path):
            self.assertFalse(fixed.auto_approval_enabled())

    def test_the_switch_is_on_only_when_it_says_so(self):
        with mock.patch.object(fixed, "AUTO_APPROVAL", self.path):
            self.write({"version": 1, "enabled": True})
            self.assertTrue(fixed.auto_approval_enabled(os.geteuid()))
            self.write({"version": 1, "enabled": False})
            self.assertFalse(fixed.auto_approval_enabled(os.geteuid()))

    def test_any_other_shape_means_off(self):
        for data in ({"version": 1}, {"version": 1, "enabled": True, "extra": 1},
                     {"version": 2, "enabled": True}, {"enabled": True}, []):
            with mock.patch.object(fixed, "AUTO_APPROVAL", self.path):
                self.write(data)
                self.assertFalse(fixed.auto_approval_enabled(os.geteuid()), data)

    def test_a_file_anybody_else_can_write_means_off(self):
        with mock.patch.object(fixed, "AUTO_APPROVAL", self.path):
            self.write({"version": 1, "enabled": True}, mode=0o644)
            self.assertFalse(fixed.auto_approval_enabled(os.geteuid()))

    def test_a_file_that_is_not_json_means_off(self):
        with mock.patch.object(fixed, "AUTO_APPROVAL", self.path):
            self.path.write_text("not json")
            self.path.chmod(0o600)
            self.assertFalse(fixed.auto_approval_enabled(os.geteuid()))


class VersionTest(unittest.TestCase):
    def test_a_version_is_three_numbers_with_a_v(self):
        self.assertEqual(fixed.parse_version("v1.2.3"), (1, 2, 3))
        for bad in ("1.2.3", "v1.2", "v1.2.3.4", "vx.y.z", "", None, 3):
            with self.assertRaises(fixed.Rejected):
                fixed.parse_version(bad)

    def test_a_breaking_change_moves_the_major_number(self):
        self.assertEqual(fixed.commit_kind(["feat(a): add a thing"]), "minor")
        self.assertEqual(fixed.commit_kind(["fix(a): mend a thing"]), "patch")
        self.assertEqual(fixed.commit_kind(["feat(a): add a thing\n\nBREAKING CHANGE: no"]),
                         "major")
        self.assertEqual(fixed.commit_kind(["feat(a)!: add a thing"]), "major")
        self.assertEqual(fixed.commit_kind(["docs: write it down"]), "patch")

    def test_a_feature_anywhere_in_the_range_moves_the_minor_number(self):
        self.assertEqual(fixed.commit_kind(["fix: mend", "feat: add", "fix: mend again"]),
                         "minor")

    def test_the_version_only_moves_forward(self):
        answers = []
        for kind in ("patch", "minor", "major"):
            with mock.patch.object(fixed.verifier, "get_json", return_value=compare("fix: mend")), \
                 mock.patch.object(fixed, "commit_kind", return_value=kind):
                answers.append(fixed.next_version("v1.2.3", "a" * 40, "b" * 40, b"token"))
        self.assertEqual(answers, ["v1.2.4", "v1.3.0", "v2.0.0"])

    def test_the_first_release_is_the_first_version(self):
        with mock.patch.object(fixed.verifier, "get_json", return_value=compare("fix: mend")), \
             mock.patch.object(fixed, "commit_kind", return_value="patch"):
            self.assertEqual(fixed.next_version(None, "a" * 40, "b" * 40, b"token"), "v1.0.1")

    def test_a_failure_to_read_the_commits_never_stops_a_deployment(self):
        def refuse(*_args, **_kwargs):
            raise fixed.verifier.Unverified("GitHub evidence unavailable")

        with mock.patch.object(fixed.verifier, "get_json", side_effect=refuse):
            self.assertEqual(fixed.next_version("v1.2.3", "a" * 40, "b" * 40, b"token"),
                             "v1.2.4")

    def test_an_unexpected_range_falls_back_to_a_patch(self):
        with mock.patch.object(fixed.verifier, "get_json",
                               return_value={"status": "identical", "ahead_by": 0, "commits": []}):
            self.assertEqual(fixed.next_version("v1.2.3", "a" * 40, "b" * 40, b"token"),
                             "v1.2.4")

    def test_the_range_is_read_from_the_commits_github_reports(self):
        answered = compare("feat(deploy): deploy by itself")
        with mock.patch.object(fixed.verifier, "get_json", return_value=answered):
            self.assertEqual(fixed.next_version("v1.2.3", "a" * 40, "b" * 40, b"token"),
                             "v1.3.0")


class TaggedVersionTest(unittest.TestCase):
    """The name the repository gives a release is the version that is kept."""

    def release(self, commit="b" * 40):
        return {"repository": "feerozmandi/xennic-website", "commit": commit,
                "digest": "sha256:" + "c" * 64, "platform": "linux/amd64", "run_number": 7}

    def test_the_tag_that_carries_the_commit_is_the_version(self):
        with mock.patch.object(fixed.verifier, "release_version", return_value="v1.4.0") as named:
            self.assertEqual(fixed.tagged_version(self.release(), "v1.3.0", b"token"), "v1.4.0")
            named.assert_called_once_with("b" * 40, b"token")

    def test_the_first_release_takes_the_name_it_was_given(self):
        with mock.patch.object(fixed.verifier, "release_version", return_value="v1.4.0"):
            self.assertEqual(fixed.tagged_version(self.release(), None, b"token"), "v1.4.0")

    def test_a_name_that_does_not_move_forward_is_refused(self):
        with mock.patch.object(fixed.verifier, "release_version", return_value="v1.3.0"):
            self.assertIsNone(fixed.tagged_version(self.release(), "v1.3.0", b"token"))
        with mock.patch.object(fixed.verifier, "release_version", return_value="v1.2.9"):
            self.assertIsNone(fixed.tagged_version(self.release(), "v1.3.0", b"token"))

    def test_a_name_that_cannot_be_read_leaves_the_computed_version_in_charge(self):
        def refuse(*_args, **_kwargs):
            raise fixed.verifier.Unverified("GitHub evidence unavailable")

        with mock.patch.object(fixed.verifier, "release_version", side_effect=refuse):
            self.assertIsNone(fixed.tagged_version(self.release(), "v1.3.0", b"token"))

    def test_a_name_that_is_not_a_version_is_refused(self):
        with mock.patch.object(fixed.verifier, "release_version", return_value="release-1"):
            self.assertIsNone(fixed.tagged_version(self.release(), "v1.3.0", b"token"))


class TransitionGateTest(unittest.TestCase):
    """The gate reads the reviewed file; the automatic rule only fills a gap."""

    def setUp(self):
        self.rows = [{"from_commit": "a" * 40, "to_commit": "b" * 40,
                      "migration_sha256": "c" * 64, "previous_migrations": ["one"],
                      "rollback_safe": True}]
        self.previous = {"commit": "a" * 40}
        self.candidate = {"commit": "b" * 40, "run_number": 7}

    def test_a_reviewed_row_is_used_as_it_is(self):
        with mock.patch.object(fixed, "transition_rows", return_value=self.rows):
            self.assertEqual(fixed.authorize_transition(self.previous, self.candidate),
                             self.rows[0])

    def test_a_broken_row_is_refused_and_never_replaced_by_the_automatic_rule(self):
        broken = [dict(self.rows[0], rollback_safe=False)]
        with mock.patch.object(fixed, "transition_rows", return_value=broken):
            with self.assertRaises(fixed.Rejected):
                fixed.authorize_transition(self.previous, self.candidate)

    def test_without_a_row_the_automatic_rule_decides(self):
        with mock.patch.object(fixed, "transition_rows", return_value=[]):
            with mock.patch.object(fixed, "auto_approve",
                                   return_value={"to_commit": "b" * 40}) as rule:
                self.assertEqual(fixed.authorize_transition(self.previous, self.candidate),
                                 {"to_commit": "b" * 40})
        rule.assert_called_once()


class AutomaticApprovalTest(unittest.TestCase):
    """The rule itself: identical migration files and no new migration."""

    def setUp(self):
        self.previous = {"commit": "a" * 40, "run_number": 6}
        self.candidate = {"commit": "b" * 40, "run_number": 7}
        self.tree = entries("app/migrations/index.ts", "app/migrations/one.ts")

    def approve(self, *, enabled=True, candidate=None, running=None, ledger=None):
        with mock.patch.object(fixed, "auto_approval_enabled", return_value=enabled), \
             mock.patch.object(fixed, "pull_candidate"), \
             mock.patch.object(fixed, "image_migration_entries",
                               return_value=self.tree if candidate is None else candidate), \
             mock.patch.object(fixed, "running_migration_entries",
                               return_value=self.tree if running is None else running), \
             mock.patch.object(fixed, "running_app_id", return_value="d" * 64), \
             mock.patch.object(fixed, "migration_ledger",
                               return_value=["one"] if ledger is None else ledger), \
             mock.patch.object(fixed, "transition_rows", return_value=[]), \
             mock.patch.object(fixed, "write_transitions") as writer:
            row = fixed.auto_approve(self.previous, self.candidate)
        return row, writer

    def test_an_identical_tree_with_no_new_migration_is_approved(self):
        row, writer = self.approve()
        self.assertEqual(row["from_commit"], "a" * 40)
        self.assertEqual(row["to_commit"], "b" * 40)
        self.assertEqual(row["previous_migrations"], ["one"])
        self.assertIs(row["rollback_safe"], True)
        self.assertTrue(writer.called)

    def test_the_switch_is_the_only_way_in(self):
        with self.assertRaises(fixed.Rejected):
            self.approve(enabled=False)

    def test_a_changed_migration_file_is_refused(self):
        with self.assertRaises(fixed.Rejected):
            self.approve(running=entries("app/migrations/index.ts", "app/migrations/two.ts"))

    def test_a_new_migration_is_refused(self):
        with self.assertRaises(fixed.Rejected):
            self.approve(ledger=["one", "two"])

    def test_a_ledger_the_image_does_not_declare_is_refused(self):
        with self.assertRaises(fixed.Rejected):
            self.approve(ledger=["two"])

    def test_a_tree_without_migrations_is_refused(self):
        with self.assertRaises(fixed.Rejected):
            self.approve(candidate=entries("app/migrations/001-init.sql"))


if __name__ == "__main__":
    unittest.main()
