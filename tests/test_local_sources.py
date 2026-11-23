import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from local_sources import collect_git, window


class WindowTests(unittest.TestCase):
    def test_elapsed_time_across_clock_change(self):
        end = datetime(2026, 10, 25, 8, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        for mode, count, hours in (("morning", None, 24), ("evening", None, 9),
                                   ("week", None, 168), ("days", "7", 168), ("hours", 3, 3)):
            start, stop = window(mode, count, end)
            self.assertEqual(start.tzinfo, timezone.utc)
            self.assertEqual(stop, end.astimezone(timezone.utc))
            self.assertEqual(stop - start, timedelta(hours=hours))
        self.assertEqual(window("morning", end=end)[0].astimezone(end.tzinfo).hour, 9)

    def test_invalid_window(self):
        for count in (None, 0, -1, True, "2.5", 1.5, 10**12):
            with self.assertRaises(ValueError):
                window("hours", count)
        with self.assertRaises(ValueError):
            window("week", end=datetime(2026, 11, 23))


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "workspace repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "writer@example.org")
        self.tree = self.git("mktree", input_data="")
        self.start = datetime(2026, 11, 23, 8, tzinfo=timezone.utc)
        self.end = self.start + timedelta(hours=9)

    def git(self, *args, env=None, input_data=None):
        options = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        options.update(env or {})
        return subprocess.run(["git", "-C", str(self.repo), *args], input=input_data,
                              env=options, text=True, capture_output=True, check=True).stdout.strip()

    def commit(self, name, when, parent=None, author="writer@example.org"):
        date = when.isoformat()
        env = dict(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date,
                   GIT_AUTHOR_NAME="Example", GIT_COMMITTER_NAME="Example",
                   GIT_AUTHOR_EMAIL=author, GIT_COMMITTER_EMAIL="writer@example.org")
        parents = ["-p", parent] if parent else []
        return self.git("commit-tree", self.tree, *parents, "-m", name, env=env)

    def collect(self, path):
        records, gaps = [], []
        summary = collect_git(path, self.start, self.end, records.append, gaps.append)
        return records, gaps, summary

    def test_boundaries_clock_skew_detached_head_and_local_refs(self):
        lower = self.commit("Exactly at start", self.start)
        skewed_child = self.commit("Older child", self.start - timedelta(days=2), lower)
        upper = self.commit("Exactly at end", self.end, skewed_child)
        self.git("update-ref", "refs/heads/main", upper)
        side = self.commit("Colleague's change", self.start + timedelta(hours=1),
                           lower, "colleague@example.org")
        self.git("update-ref", "refs/heads/side", side)
        self.git("update-ref", "refs/heads/side-alias", side)
        detached = self.commit("Detached work", self.start + timedelta(hours=3))
        self.git("update-ref", "--no-deref", "HEAD", detached)
        remote = self.commit("Remote-only", self.start + timedelta(hours=4))
        self.git("update-ref", "refs/remotes/origin/unmerged", remote)
        nested = self.repo / "component"
        nested.mkdir()
        records, gaps, summary = self.collect(nested)
        self.assertEqual(gaps, [])
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(Path(summary["repository"]).resolve(), self.repo.resolve())
        by_hash = {r["id"]: r for r in records}
        self.assertEqual(set(by_hash), {lower, side, detached})
        self.assertEqual(by_hash[lower]["timestamp"], self.start.isoformat())
        self.assertTrue(by_hash[lower]["matches_git_identity"])
        self.assertFalse(by_hash[side]["matches_git_identity"])
        self.assertEqual(by_hash[side]["subject"], "Colleague's change")
        self.start += timedelta(microseconds=1)
        self.assertNotIn(lower, {r["id"] for r in self.collect(nested)[0]})

    def test_empty_and_non_repository(self):
        records, gaps, summary = self.collect(self.repo)
        self.assertEqual((records, gaps, summary["status"]), ([], [], "ok"))
        records, gaps, summary = self.collect(self.repo.parent)
        self.assertEqual((records, gaps, summary["status"]), ([], [], "not_a_repository"))

    def test_shallow_clone_reports_gap(self):
        parent = self.commit("Parent", self.start)
        tip = self.commit("Tip", self.start + timedelta(hours=1), parent)
        self.git("update-ref", "refs/heads/main", tip)
        clone = self.repo.parent / "clone"
        self.git("clone", "-q", "--no-local", "--depth=1", str(self.repo), str(clone))
        records, gaps, summary = self.collect(clone)
        self.assertEqual([r["id"] for r in records], [tip])
        self.assertTrue(gaps)
        self.assertEqual(summary["status"], "partial")


if __name__ == "__main__":
    unittest.main()
