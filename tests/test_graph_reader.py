import io
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import graph_reader as graph


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, tzinfo=timezone.utc)
CHANNEL_URL = ("https://teams.microsoft.com/l/channel/19%3Ademo%40thread.tacv2/Release%20planning"
               "?groupId=90000000-0000-4000-8000-000000000001&tenantId=90000000-0000-4000-8000-000000000002")


class GraphReaderTests(unittest.TestCase):
    def collect(self, service, get, **kwargs):
        records, gaps = [], []
        with patch.object(graph, "_get", side_effect=get):
            graph.collect(service, "fixture", START, END, records.append, gaps.append, **kwargs)
        return records, gaps

    def test_chat_pagination_edits_reactions_and_partial_permission(self):
        first = {"id": "1", "createdDateTime": "2026-01-01T00:00:00.0000000Z", "messageType": "message",
                 "from": {"user": {"id": "user-1", "displayName": "Alex"}},
                 "body": {"contentType": "html", "content": "<p>Initial <b>plan</b></p><style>hidden</style>"},
                 "attachments": [{"name": "private-file"}], "webUrl": "javascript:doSomething()"}
        old = dict(first, id="2", createdDateTime="2025-12-01T12:00:00Z")
        edited = dict(old, id="3", lastEditedDateTime="2026-01-01T12:10:00.2Z")
        second_chat = graph.GRAPH + "/me/chats?next=c2"
        second_page = graph.GRAPH + "/me/chats/open/messages?next=p2"

        def get(url, token, service):
            if url == second_chat:
                return {"value": [{"id": "closed"}, {"id": "open"}]}
            if url == second_page:
                return {"value": [first, edited, old, dict(first, id="4", deletedDateTime="now"),
                                  dict(first, id="5", createdDateTime="2026-01-02T00:00:00Z")]}
            path = urlsplit(url).path
            if path.endswith("/chats"):
                return {"value": [{"id": "open", "topic": "Atlas"}], "@odata.nextLink": second_chat}
            if path.endswith("/closed/messages"):
                raise graph.ReadError("Access denied (403)")
            query = parse_qs(urlsplit(url).query)
            self.assertEqual(query["$orderby"], ["lastModifiedDateTime desc"])
            self.assertIn("2025-12-31T23:59:59.999000Z", query["$filter"][0])
            return {"value": [first], "@odata.nextLink": second_page}

        rows, gaps = self.collect("teams", get, user_id="user-1")
        self.assertEqual([r["id"] for r in rows], ["open/1", "open/3"])
        self.assertEqual([r["time_kind"] for r in rows], ["created", "edited"])
        self.assertEqual(rows[0]["direction"], "sent")
        self.assertEqual(rows[0]["text"], "Initial plan")
        self.assertIsNone(rows[0]["link"])
        self.assertEqual([g["scope"] for g in gaps], ["chat open", "chat closed"])

    def test_later_reaction_retains_message_and_later_edits_cannot_backdate_text(self):
        created = {"id": "visible", "messageType": "message", "createdDateTime": "2026-01-01T15:00:00Z",
                   "lastModifiedDateTime": "2026-01-03T10:00:00Z",
                   "body": {"contentType": "text", "content": "Original work"}}
        changed = dict(created, id="changed", lastEditedDateTime="2026-01-03T10:00:00Z",
                       body={"contentType": "text", "content": "Later decision"})
        def get(url, token, service):
            if urlsplit(url).path.endswith("/chats"):
                return {"value": [{"id": "group", "webUrl": "https://other.example/x"}]}
            self.assertNotIn(" lt ", parse_qs(urlsplit(url).query)["$filter"][0])
            return {"value": [created, changed, dict(changed, id="also-changed"),
                              dict(changed, id="future", createdDateTime="2026-01-03T10:00:00Z")]}
        rows, gaps = self.collect("teams", get)
        self.assertEqual([r["text"] for r in rows], ["Original work"])
        self.assertIsNone(rows[0]["link"])
        self.assertEqual(len(gaps), 1)
        self.assertIn("unavailable", gaps[0]["reason"])

    def test_channel_link_keeps_standard_routing_only(self):
        parsed = graph.parse_channel_link(CHANNEL_URL + "&ngc=true&allowXTenantAccess=true&label=unwanted")
        self.assertEqual(parsed["title"], "Release planning")
        self.assertEqual(parsed["channel_id"], "19:demo@thread.tacv2")
        self.assertEqual(parsed["tenant_id"], "90000000-0000-4000-8000-000000000002")
        self.assertNotIn("unwanted", parsed["link"])
        self.assertIn("allowXTenantAccess=true", parsed["link"])
        self.assertEqual(graph.parse_channel_link(parsed["link"]), parsed)
        for url in (CHANNEL_URL.replace("teams.microsoft.com", "other.example"),
                    CHANNEL_URL.replace("/l/channel/", "/l/message/"),
                    CHANNEL_URL.replace("19%3Ademo", "19%3Ademo%2F.."),
                    CHANNEL_URL.split("?")[0], CHANNEL_URL.replace("groupId=", "groupId=invalid"),
                    CHANNEL_URL + "&access_token=secret", CHANNEL_URL + "&groupId=duplicate"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                graph.parse_channel_link(url)

    def test_channel_replies_on_old_posts_and_safe_early_exit(self):
        channel = graph.parse_channel_link(CHANNEL_URL)
        collection = f"{graph.GRAPH}/teams/{channel['team_id']}/channels/{channel['channel_id']}/messages"
        root_page = collection + "?next=page"
        reply_page = collection + "/old/replies?next=overflow"
        too_old = collection + "?next=too-old"
        old = "2025-12-07T12:00:00Z"
        recent = "2026-01-01T13:00:00Z"

        def msg(ident, date, **fields):
            return {"id": ident, "createdDateTime": date, "lastModifiedDateTime": date, "messageType": "message",
                    "from": {"user": {"id": "me", "displayName": "Alex"}}, "body": {"content": ident}, **fields}

        paths = []
        def get(url, token, service):
            paths.append(url)
            self.assertEqual(service, "channels")
            if url == reply_page:
                return {"value": [msg("in-window reply", recent), msg("ignored", "2026-02-01T00:00:00Z")]}
            if url == root_page:
                return {"value": [msg("visible root", recent, replies=[msg("in-window reply", recent)]),
                                  msg("old chain", old, replies=[])], "@odata.nextLink": too_old}
            self.assertNotEqual(url, too_old)
            self.assertIn(channel["team_id"], url)
            self.assertEqual(parse_qs(urlsplit(url).query)["$expand"], ["replies"])
            return {"value": [msg("old", old, **{"replies": [msg("old reply", old)],
                                                 "replies@odata.nextLink": reply_page})],
                    "@odata.nextLink": root_page}

        rows, gaps = self.collect("channels", get, channels=[channel, channel], user_id="me")
        self.assertEqual([r["text"] for r in rows], ["in-window reply", "visible root", "in-window reply"])
        self.assertEqual(len({r["id"] for r in rows}), 3)  # Reply IDs are scoped to their parent.
        self.assertEqual(rows[0]["reply_to_id"], "old")
        self.assertEqual(rows[0]["direction"], "sent")
        self.assertEqual(rows[0]["link"], channel["link"])
        self.assertEqual(gaps, [])
        self.assertEqual(len(paths), 3)

    def test_channel_reply_failure_does_not_hide_later_posts(self):
        channel = graph.parse_channel_link(CHANNEL_URL)
        def get(url, *_):
            self.assertNotIn("untrusted", url)
            self.assertNotIn("unselected", url)
            base = {"createdDateTime": "2026-01-01T15:00:00Z", "messageType": "message"}
            return {"value": [dict(base, id="one", **{"replies": [], "replies@odata.nextLink": "https://untrusted/x"}),
                              dict(base, id="two", replies=[]),
                              dict(base, id="three", **{"replies": [],
                                   "replies@odata.nextLink": graph.GRAPH + "/teams/unselected/channels/x/messages"})]}
        rows, gaps = self.collect("channels", get, channels=[channel])
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(gaps), 2)
        self.assertIn("replies one", gaps[0]["scope"])
        self.assertIn("outside the selected channel", gaps[1]["reason"])

    def test_mailbox_filed_mail_sent_precedence_and_exclusions(self):
        def mail(ident, **updates):
            row = {"id": ident, "isDraft": False, "subject": "Budget", "parentFolderId": "inbox-id",
                   "sentDateTime": "2026-01-01T09:00:00Z", "receivedDateTime": "2026-01-01T09:05:00Z",
                   "sender": {"emailAddress": {"name": "Alex"}}, "internetMessageId": "<" + ident + ">",
                   "uniqueBody": {"contentType": "Text", "content": "Decision"},
                   "body": {"contentType": "text", "content": "old quoted history"}}
            row.update(updates)
            return row

        def get(url, token, service):
            path = urlsplit(url).path
            if path.endswith("/inbox"):
                return {"id": "inbox-id"}
            query = parse_qs(urlsplit(url).query)
            self.assertIn("uniqueBody", query["$select"][0])
            if path.endswith("/sentitems/messages"):
                self.assertIn("sentDateTime ge", query["$filter"][0])
                return {"value": [mail("sent")]}
            self.assertIn("receivedDateTime ge", query["$filter"][0])
            return {"value": [mail("sent"), mail("copy", internetMessageId="<sent>"), mail("in"),
                              mail("filed", parentFolderId="customer"), mail("draft", isDraft=True),
                              mail("too late", receivedDateTime="2026-01-02T00:00:00Z")]}

        rows, gaps = self.collect("outlook", get)
        self.assertEqual(gaps, [])
        self.assertEqual([(r["id"], r["direction"]) for r in rows],
                         [("sent", "sent"), ("in", "received"), ("filed", "mailbox")])
        self.assertEqual([r["text"] for r in rows], ["Decision"] * 3)
        self.assertEqual(rows[0]["time"], "2026-01-01T09:00:00Z")

    def test_untrusted_or_looping_continuation_does_not_make_another_request(self):
        for next_url in ("https://other.example/v1.0/me/chats", "https://graph.microsoft.com@bad.example/v1.0/x",
                         "https://graph.microsoft.com/v1.0/me/chats?access_token=hidden", "http://graph.microsoft.com/x",
                         graph._query("/me/chats", **{"$top": 50, "$expand": "members"})):
            with self.subTest(next_url=next_url):
                calls = []
                def get(url, token, service):
                    calls.append(url)
                    return {"value": [], "@odata.nextLink": next_url}
                rows, gaps = self.collect("teams", get)
                self.assertFalse(rows)
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(gaps), 1)
                self.assertNotIn("hidden", str(gaps))

    def test_auth_and_permission_are_distinct_without_leaking_response(self):
        for status, expected in ((401, graph.AuthenticationRequired), (403, graph.ReadError),
                                 (302, graph.ReadError)):
            with self.subTest(status=status), patch.object(graph, "build_opener") as opener:
                opener.return_value.open.side_effect = HTTPError("private-url", status, "private-body", {}, None)
                with self.assertRaises(expected) as error:
                    graph._get(graph.GRAPH + "/me/chats", "fixture-secret", "teams")
                self.assertNotIn("private", str(error.exception))
                self.assertNotIn("fixture-secret", str(error.exception))
                self.assertIsInstance(opener.call_args.args[0], graph._NoRedirect)
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.get_method(), "GET")

    def test_auth_propagates_after_partial_page_and_throttle_is_bounded(self):
        def fail(*args):
            raise graph.AuthenticationRequired("reauthenticate")
        with self.assertRaises(graph.AuthenticationRequired):
            self.collect("outlook", fail)
        with patch.object(graph, "build_opener") as opener, patch.object(graph.time, "sleep") as sleep:
            opener.return_value.open.side_effect = [
                HTTPError("url", 429, "", {"Retry-After": "2"}, None), io.BytesIO(b'{"value":[]}')]
            self.assertEqual(graph._get(graph.GRAPH + "/me/chats", "fixture", "teams"), {"value": []})
            sleep.assert_called_once_with(2)
            opener.return_value.open.side_effect = HTTPError("url", 429, "", {"Retry-After": "80"}, None)
            with self.assertRaises(graph.ServiceUnavailable):
                graph._get(graph.GRAPH + "/me/chats", "fixture", "teams")
            self.assertEqual(sleep.call_count, 1)


if __name__ == "__main__":
    unittest.main()
