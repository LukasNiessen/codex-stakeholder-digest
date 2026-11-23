import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, call, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import digest


class CommandTests(unittest.TestCase):
    def test_wizard_links_multiple_accounts_and_advances(self):
        store = Mock(project="/project")
        store.bound.return_value = []
        store.available.side_effect = lambda service: ["Shared"] if service == "teams" else []
        answers = ["yes", "Shared", "no", "Customer", "public-id", "tenant-id", "no", "cancel",
                   "yes", "Personal", "", "", ""]
        with patch("builtins.input", side_effect=answers), redirect_stdout(io.StringIO()):
            digest.wizard(store)
        store.bind.assert_called_once_with("teams", "Shared")
        self.assertEqual(store.connect.call_args_list, [
            call("teams", "Customer", "public-id", "tenant-id"),
            call("outlook", "Personal", "public-id", "tenant-id"),
        ])
        store.unbind.assert_not_called()

    def test_channel_selection_uses_the_chosen_teams_alias(self):
        store = Mock()
        store.channels.return_value = []
        link = "https://teams.microsoft.com/l/channel/19%3Achat%40thread.tacv2/Delivery?groupId=ee924cd1-2461-4200-84a0-1ae1ee72e022"
        with patch("builtins.input", side_effect=["yes", link, "cancel"]), redirect_stdout(io.StringIO()):
            digest.wizard_channels(store, "Consulting")
        alias, channel = store.add_channel.call_args.args
        self.assertEqual(alias, "Consulting")
        self.assertEqual(channel["channel_id"], "19:chat@thread.tacv2")
        self.assertEqual(channel["title"], "Delivery")
        store.unbind.assert_not_called()

    def test_selection_keeps_valid_nicknames_and_never_substitutes(self):
        store = Mock()
        store.bound.side_effect = lambda s: ["One", "Two"] if s == "teams" else ["One"]
        accounts, missing = digest.choose_accounts(store, ["teams", "outlook"], ["oNe", "absent"])
        self.assertEqual(accounts, [("teams", "One"), ("outlook", "One")])
        self.assertEqual(missing, ["absent"])

    def test_stale_token_retries_same_window_and_deduplicates(self):
        store = Mock()
        store.token.side_effect = ["old", "refreshed", "reauthenticated"]
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=9)
        attempts = []

        def graph(service, token, lower, upper, record, gap, **kw):
            attempts.append((token, lower, upper))
            record({"id": "duplicate"})
            if token != "reauthenticated":
                gap({"scope": "old-attempt", "reason": "later recovered"})
                raise digest.AuthenticationRequired()
            record({"id": "new"})

        rows = []
        with patch.object(digest, "collect_graph", graph), redirect_stderr(io.StringIO()):
            digest.read_account(store, "teams", "Customer", start, end, True, rows.append)
        self.assertEqual([r.get("id") for r in rows if r["kind"] == "record"], ["duplicate", "new"])
        self.assertEqual(rows[-1]["status"], "ok")
        self.assertEqual(rows[-1]["count"], 2)
        self.assertEqual(attempts, [(t, start, end) for t in ["old", "refreshed", "reauthenticated"]])
        store.reconnect.assert_called_once_with("teams", "Customer")

    def test_skipped_signin_is_a_gap(self):
        store = Mock()
        store.token.side_effect = digest.AuthRequired("Requires sign-in")
        end = datetime.now(timezone.utc)
        rows = []
        digest.read_account(store, "outlook", "Shared", end - timedelta(hours=1), end,
                            False, rows.append)
        self.assertEqual(rows[0]["kind"], "gap")
        self.assertEqual(rows[0]["account"], "Shared")
        self.assertEqual(rows[-1]["status"], "partial")
        store.reconnect.assert_not_called()

    def test_private_cli_output_and_local_only_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_CONFIG_HOME=tmp + "/config", TMPDIR=tmp)
            cli = [sys.executable, "-B", str(SCRIPTS / "digest.py"), "--workspace", tmp, "collect"]
            run = subprocess.run(cli + ["hours", "4", "--end", "2026-11-19T01:00:00+01:00",
                                        "--private-file"], env=env, check=True, capture_output=True, text=True)
            path = Path(json.loads(run.stdout)["evidence_file"])
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(rows[0]["start"], "2026-11-18T20:00:00+00:00")
            self.assertEqual(rows[0]["end"], "2026-11-19T00:00:00+00:00")
            self.assertEqual({r["status"] for r in rows[1:]}, {"not_a_repository", "no_selected_account"})
            self.assertFalse((Path(tmp) / "config").exists())
            invalid = subprocess.run(cli + ["hours", "0"], env=env, capture_output=True)
            self.assertNotEqual(invalid.returncode, 0)


if __name__ == "__main__":
    unittest.main()
