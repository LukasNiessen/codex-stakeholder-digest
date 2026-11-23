"""Offline account selection, sign-in and renewal checks. No native store is touched."""
import base64
import concurrent.futures
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from accounts import AccountError, AccountStore, AuthRequired


CLIENT = "10000000-0000-0000-0000-000000000001"
TENANT = "20000000-0000-0000-0000-000000000002"
USER = "30000000-0000-0000-0000-000000000003"
OTHER = "40000000-0000-0000-0000-000000000004"


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "config")})
        env.start()
        self.addCleanup(env.stop)
        for name in ("first", "second"):
            (self.root / name).mkdir()
        self.first = AccountStore(self.root / "first")
        self.second = AccountStore(self.root / "second")

        self.msal = Mock()
        self.session = Mock()
        self.app = self.msal.PublicClientApplication.return_value
        self.cache = self.msal.SerializableTokenCache.return_value
        self.cache.serialize.return_value = "synthetic serialized token material"
        self.cache.has_state_changed = False
        mock = patch("accounts._msal_cache", return_value=(self.msal, self.session, FileNotFoundError))
        self.backend = mock.start()
        self.addCleanup(mock.stop)
        self.success = {
            "scope": "openid profile Chat.Read",
            "access_token": "synthetic delegated access token",
            "id_token_claims": {"tid": TENANT, "oid": USER},
        }
        self.app.acquire_token_interactive.return_value = self.success
        self.app.get_accounts.return_value = [{"realm": TENANT, "local_account_id": USER}]
        self.app.acquire_token_silent_with_error.return_value = self.success

    def test_empty_store_reads_do_not_create_anything(self):
        self.assertEqual(self.first.bound("teams"), [])
        self.assertEqual(self.first.available("outlook"), [])
        self.assertFalse((self.root / "config").exists())
        self.backend.assert_not_called()

    def test_bindings_can_be_reused_independently_without_implicit_access(self):
        self.first.connect("teams", "Client West", CLIENT, TENANT)
        self.app.acquire_token_interactive.assert_called_once_with(
            scopes=["Chat.Read"], prompt="select_account", timeout=300)
        self.assertEqual(self.second.available("teams"), ["Client West"])
        self.assertEqual(self.second.bound("teams"), [])
        with self.assertRaisesRegex(AccountError, "not enabled"):
            self.second.token("teams", "Client West")
        self.second.bind("teams", "CLIENT WEST")
        self.assertEqual(self.second.user_id("teams", "client west"), USER)
        self.assertEqual(self.second.bound("outlook"), [])
        self.first.unbind("teams", "CLIENT WEST")
        self.assertEqual(self.first.bound("teams"), [])
        self.assertEqual(self.second.bound("teams"), ["Client West"])
        for path in (self.root / "config").rglob("*"):
            if path.is_file():
                self.assertNotIn(b"synthetic", path.read_bytes())

    def test_silent_renewal_writes_rotated_cache_without_reopening_browser(self):
        self.first.connect("teams", "West", CLIENT, TENANT)
        self.app.acquire_token_interactive.reset_mock()
        self.session.save.reset_mock()
        self.cache.has_state_changed = True
        self.assertEqual(self.first.token("teams", "West", force_refresh=True), self.success["access_token"])
        self.app.acquire_token_silent_with_error.assert_called_once_with(
            ["Chat.Read"], account={"realm": TENANT, "local_account_id": USER}, force_refresh=True)
        self.app.acquire_token_interactive.assert_not_called()
        self.session.save.assert_called_once_with("synthetic serialized token material")

    def test_revocation_and_missing_cache_resume_with_same_account_only(self):
        self.first.connect("teams", "West", CLIENT)
        self.session.save.reset_mock()
        self.app.acquire_token_silent_with_error.return_value = {"error": "invalid_grant"}
        with self.assertRaises(AuthRequired):
            self.first.token("teams", "West")
        for claims in ({"tid": OTHER, "oid": USER}, {"tid": TENANT, "oid": OTHER}):
            self.app.acquire_token_interactive.return_value = {**self.success, "id_token_claims": claims}
            with self.assertRaisesRegex(AccountError, "another account or directory"):
                self.first.token("teams", "West", interactive=True)
        self.session.save.assert_not_called()
        self.session.load.side_effect = FileNotFoundError
        self.app.acquire_token_interactive.return_value = self.success
        self.assertEqual(self.first.token("teams", "West", interactive=True), self.success["access_token"])
        self.assertEqual(self.first.user_id("teams", "West"), USER)
        self.session.save.assert_called_once()

    def test_permission_denied_or_store_unavailable_does_not_bind(self):
        self.app.acquire_token_interactive.return_value = {**self.success, "scope": "openid"}
        with self.assertRaisesRegex(AuthRequired, "Mail.Read"):
            self.first.connect("outlook", "West", CLIENT)
        self.session.save.assert_not_called()
        self.assertEqual(self.first.available("outlook"), [])
        self.app.acquire_token_interactive.return_value = self.success
        self.session.save.side_effect = ValueError("simulated raw auth details")
        with self.assertRaises(AccountError) as err:
            self.first.connect("teams", "West", CLIENT)
        self.assertNotIn("raw auth details", str(err.exception))
        self.assertEqual(self.first.bound("teams"), [])

    def test_concurrent_binds_preserve_separate_aliases(self):
        self.first.connect("teams", "West", CLIENT)
        self.first.connect("teams", "East", CLIENT)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda name: self.second.bind("teams", name), ["West", "East"]))
        self.assertEqual(self.second.bound("teams"), ["East", "West"])

    def test_channels_opt_in_per_project_and_share_only_the_consent(self):
        self.first.connect("teams", "West", CLIENT)
        team_cache = self.backend.call_args.args[0]
        selected = {"team_id": CLIENT, "channel_id": "channel-1", "title": "Delivery",
                    "link": "https://teams.microsoft.com/l/channel/channel-1/Delivery", "tenant_id": TENANT}
        second = {**selected, "channel_id": "channel-2", "title": "Platform"}
        allowed = {**self.success, "scope": "ChannelMessage.Read.All"}
        self.app.acquire_token_interactive.return_value = allowed
        self.app.acquire_token_silent_with_error.return_value = allowed
        self.first.add_channel("West", selected)
        self.assertNotEqual(self.backend.call_args.args[0], team_cache)
        self.app.acquire_token_interactive.assert_called_with(
            scopes=["ChannelMessage.Read.All"], prompt="select_account", timeout=300)
        self.app.acquire_token_interactive.reset_mock()
        self.second.bind("teams", "West")
        self.assertEqual(self.second.bound("channels"), [])
        self.assertEqual(self.second.channels("West"), [])
        with self.assertRaises(AccountError):
            self.second.token("channels", "West")
        self.second.add_channel("WEST", second)
        self.first.add_channel("West", selected)
        self.assertEqual(self.first.channels("West"), [selected])
        self.assertEqual(self.second.channels("West"), [second])
        self.app.acquire_token_interactive.assert_not_called()
        self.assertEqual(self.second.bound("channels"), ["West"])
        self.assertEqual(self.second.user_id("channels", "West"), USER)
        self.first.unbind("teams", "West")
        self.assertEqual(self.first.channels("West"), [])
        self.assertEqual(self.first.bound("channels"), [])
        self.assertEqual(self.second.channels("West"), [second])
        self.first.bind("teams", "West")
        self.assertEqual(self.first.bound("channels"), [])
        self.second.remove_channel("West", second["channel_id"])
        self.second.remove_channel("West", second["channel_id"])
        self.assertEqual(self.second.bound("teams"), ["West"])
        self.assertEqual(self.second.bound("channels"), [])

    def test_channel_consent_must_match_attached_chat_identity(self):
        self.first.connect("teams", "West", CLIENT)
        self.app.acquire_token_interactive.reset_mock()
        channel = {"team_id": CLIENT, "channel_id": "1", "title": "Group", "link": "channel-link"}
        with self.assertRaisesRegex(AccountError, "another directory"):
            self.first.add_channel("West", {**channel, "tenant_id": OTHER})
        with self.assertRaisesRegex(AccountError, "not enabled"):
            self.second.add_channel("West", channel)
        self.app.acquire_token_interactive.assert_not_called()
        with self.assertRaisesRegex(AuthRequired, "ChannelMessage.Read.All"):
            self.first.add_channel("West", channel)
        self.app.acquire_token_interactive.return_value = {**self.success, "scope": "ChannelMessage.Read.All",
                                                           "id_token_claims": {"tid": TENANT, "oid": OTHER}}
        with self.assertRaisesRegex(AccountError, "another account"):
            self.first.add_channel("West", channel)
        self.assertEqual(self.first.bound("teams"), ["West"])
        self.assertEqual(self.first.bound("channels"), [])
        self.assertEqual(self.first.channels("West"), [])

    def test_old_bindings_are_readable_before_channel_schema_is_created(self):
        self.first.connect("teams", "West", CLIENT)
        with closing(sqlite3.connect(self.first.db)) as con:
            con.execute("DROP TABLE project_channels")
        self.assertEqual(self.first.bound("channels"), [])
        self.assertEqual(self.first.channels("West"), [])
        self.assertEqual(self.first.bound("teams"), ["West"])

    def test_worktrees_share_bindings(self):
        main = self.root / "repo"
        linked = self.root / "tree"
        subprocess.run(["git", "init", "-q", str(main)], check=True)
        subprocess.run(["git", "-C", str(main), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "initial"], check=True)
        subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", "--detach", str(linked)], check=True)
        subdir = linked / "subdir"
        subdir.mkdir()
        AccountStore(main).connect("teams", "West", CLIENT)
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "wrong-repo.git")}):
            self.assertEqual(AccountStore(subdir).bound("teams"), ["West"])

    @unittest.skipUnless(importlib.util.find_spec("msal"), "optional Microsoft libraries absent")
    def test_real_cache_from_common_authority_renews_for_pinned_guest_tenant(self):
        import msal
        from requests import Response

        # Authentication through /common yields cache realm "common". The account is
        # a guest: home uid/utid differ from its local oid/tid at the resource tenant.
        claims = {"tid": TENANT, "oid": USER, "sub": "test-subject"}
        cache = msal.SerializableTokenCache()
        client_info = base64.urlsafe_b64encode(json.dumps({"uid": OTHER, "utid": CLIENT}).encode()).decode()
        cache.add({
            "client_id": CLIENT, "scope": ["Chat.Read"], "grant_type": "authorization_code",
            "token_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "response": {"client_info": client_info, "id_token_claims": claims,
                         "access_token": "old", "refresh_token": "synthetic-refresh"},
        })
        self.first.connect("teams", "Guest", CLIENT, "common")
        self.backend.return_value = (msal, self.session, FileNotFoundError)
        self.session.load.return_value = cache.serialize()

        http = Mock()
        def response(data):
            r = Response()
            r.status_code = 200
            r._content = json.dumps(data).encode()
            return r
        host = f"https://login.microsoftonline.com/{TENANT}"
        http.get.return_value = response({"authorization_endpoint": host + "/oauth2/v2.0/authorize",
            "token_endpoint": host + "/oauth2/v2.0/token", "issuer": host + "/v2.0",
            "device_authorization_endpoint": host + "/oauth2/v2.0/devicecode"})
        http.post.return_value = response({"access_token": "renewed", "scope": "Chat.Read",
                                           "token_type": "Bearer", "expires_in": 3600})
        make_client = msal.PublicClientApplication
        def offline_client(**kwargs):
            return make_client(http_client=http, instance_discovery=False, **kwargs)
        with patch.object(msal, "PublicClientApplication", side_effect=offline_client):
            self.assertEqual(self.first.token("teams", "Guest"), "renewed")
            self.assertEqual(http.post.call_args.args[0], host + "/oauth2/v2.0/token")
            self.assertIn("renewed", self.session.save.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
