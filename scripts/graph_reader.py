"""Read delegated Microsoft Graph v1.0 evidence. No message or token is persisted."""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit
from uuid import UUID
from urllib.request import HTTPRedirectHandler, Request, build_opener


GRAPH = "https://graph.microsoft.com/v1.0"
TOKEN_PARAMS = {"access_token", "refresh_token", "id_token", "client_secret"}
MAX_TEXT = 12000


class AuthenticationRequired(Exception):
    """A Graph request returned 401. Renew the selected account and retry once."""


class ReadError(Exception):
    """A single collection could not be fully read."""


class ServiceUnavailable(Exception):
    """The account-wide collection should stop after throttling or a transport error."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _safe_url(url, graph=False):
    if not isinstance(url, str) or any(ord(c) < 33 or ord(c) == 127 for c in url):
        return False
    try:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username is not None:
            return False
        if graph and (parts.netloc.lower() not in ("graph.microsoft.com", "graph.microsoft.com:443")
                      or not parts.path.startswith("/v1.0/") or parts.fragment):
            return False
        return not any(k.lower() in TOKEN_PARAMS for fragment in (parts.query, parts.fragment)
                       for k, _ in parse_qsl(fragment))
    except ValueError:
        return False


def _get(url, token, service):
    if not _safe_url(url, graph=True):
        raise ReadError("Graph returned an invalid continuation URL")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if service == "outlook":
        headers["Prefer"] = 'IdType="ImmutableId", outlook.body-content-type="text"'
    request = Request(url, headers=headers)
    opener = build_opener(_NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=30) as response:
                page = json.load(response)
                if not isinstance(page, dict):
                    raise ReadError("Graph returned an invalid response")
                return page
        except HTTPError as exc:
            status = exc.code
            delay = exc.headers.get("Retry-After", "")
            if exc.fp is not None:
                exc.close()
            if status == 401:
                raise AuthenticationRequired("Microsoft Graph requires renewed sign-in") from None
            if status == 403:
                raise ReadError("Access denied by Graph (403). Check permissions or tenant policy.") from None
            if status not in (429, 500, 502, 503, 504):
                raise ReadError(f"Graph returned HTTP {status}") from None
            seconds = int(delay) if delay.isdigit() else 2 ** attempt
            if attempt == 2 or seconds > 60:
                raise ServiceUnavailable(f"Graph unavailable (HTTP {status}, retry later)") from None
            time.sleep(seconds)
        except (URLError, OSError, HTTPException):
            if attempt == 2:
                raise ServiceUnavailable("Microsoft Graph connection failed") from None
            time.sleep(2 ** attempt)
        except (ValueError, UnicodeError):
            raise ReadError("Graph returned an unreadable response") from None


def _pages(url, token, service, *, expected_route=None):
    visited = set()
    while url is not None:
        if not _safe_url(url, graph=True) or url in visited:
            raise ReadError("Graph returned an invalid or repeated continuation URL")
        if expected_route is not None and unquote(urlsplit(url).path) != unquote("/v1.0" + expected_route):
            raise ReadError("Graph continuation points outside the selected channel or thread")
        visited.add(url)
        page = _get(url, token, service)
        rows = page.get("value")
        if not isinstance(rows, list):
            raise ReadError("Graph response omitted its result list")
        for row in rows:
            if not isinstance(row, dict):
                raise ReadError("Graph returned an unreadable result")
            yield row
        url = page.get("@odata.nextLink")


def _query(path, **params):
    return GRAPH + path + "?" + urlencode(params)


def _utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp(value):
    if not isinstance(value, str):
        raise ReadError("Graph returned a message without a valid activity time")
    # Graph can send seven fractional digits; Python 3.9 accepts three or six.
    def microseconds(match):
        return "." + match.group(1)[:6].ljust(6, "0")
    try:
        stamp = datetime.fromisoformat(re.sub(r"\.(\d+)", microseconds, value).replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            raise ValueError
        return stamp
    except ValueError:
        raise ReadError("Graph returned an unreadable activity timestamp") from None


def _clean(value):
    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", value).split())


class _HTMLText(HTMLParser):
    """Extract visible text without resolving external content, links or attachments."""

    hidden_tags = {"script", "style", "head", "attachment", "blockquote"}
    separators = {"p", "br", "div", "li", "td", "tr", "section", "hr"}

    def __init__(self):
        super().__init__()
        self.hidden = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.hidden_tags:
            self.hidden.append(tag)
        elif tag in self.separators:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()
        elif tag in self.separators:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _body(row):
    value = row.get("uniqueBody") or row.get("body") or {}
    content = value.get("content") or ""
    if str(value.get("contentType", "")).lower() == "html":
        parser = _HTMLText()
        try:
            parser.feed(content)
            parser.close()
        except (ValueError, AssertionError):
            raise ReadError("Unreadable HTML message") from None
        content = "".join(parser.parts)
    content = _clean(content)
    return {"text": content[:MAX_TEXT], "text_truncated": len(content) > MAX_TEXT}


def _key(row):
    ident = _clean(row.get("id"))
    if not ident:
        raise ReadError("Graph returned an item without an identifier")
    return ident


def _link(value, service):
    origins = {"teams": {"teams.microsoft.com", "teams.cloud.microsoft", "teams.live.com"},
               "outlook": {"outlook.office.com", "outlook.office365.com", "outlook.cloud.microsoft",
                           "outlook.live.com"}}
    if _safe_url(value) and urlsplit(value).netloc.lower() in origins[service]:
        return value
    return None


def parse_channel_link(url):
    """Return only the team, channel, display label and standard Teams routing parameters."""
    error = "Use Teams' Copy link to channel URL with a groupId and channel name."
    if not _link(url, "teams"):
        raise ValueError(error)
    parts = urlsplit(url)
    path = re.fullmatch(r"(?:/v2)?/l/channel/([^/]+)/([^/]+)/?", parts.path)
    if not path or parts.fragment:
        raise ValueError(error)
    channel_id, name = map(unquote, path.groups())
    if not re.fullmatch(r"19:[A-Za-z0-9_:+=.-]{1,350}@thread\.(tacv2|skype)", channel_id):
        raise ValueError(error)
    if not _clean(name) or any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        raise ValueError(error)
    known = {"groupId", "tenantId", "ngc", "allowXTenantAccess"}
    params = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key not in known:
            continue
        if key in params:
            raise ValueError(error)
        if key in ("groupId", "tenantId"):
            try:
                params[key] = str(UUID(value))
            except ValueError:
                raise ValueError(error) from None
        elif value.lower() in ("true", "false"):
            params[key] = value.lower()
        else:
            raise ValueError(error)
    if "groupId" not in params:
        raise ValueError(error)
    link = (f"https://{parts.netloc.lower()}/l/channel/{quote(channel_id, safe='')}/"
            f"{quote(name, safe='')}?{urlencode(params)}")
    result = {"team_id": params["groupId"], "channel_id": channel_id, "title": _clean(name), "link": link}
    if "tenantId" in params:
        result["tenant_id"] = params["tenantId"]
    return result


def _with_gap(service, scope, read, emit_gap):
    try:
        read()
    except ReadError as exc:
        emit_gap({"service": service, "scope": scope, "reason": str(exc)})


def _chat_title(chat, user_id):
    topic = _clean(chat.get("topic"))
    if topic:
        return topic
    kind = {"oneOnOne": "Teams chat", "group": "Teams group chat",
            "meeting": "Teams meeting chat"}.get(chat.get("chatType"), "Teams chat")
    names = []
    for member in chat.get("members") or []:
        name = _clean(member.get("displayName"))
        if name and (not user_id or member.get("userId") != user_id):
            names.append(name)
    if not names:
        return kind
    suffix = ", …" if len(names) > 3 else ""
    return kind + " (" + ", ".join(names[:3]) + suffix + ")"


class _TeamsEvidence:
    def __init__(self, service, start, end, user_id, emit_record, emit_gap):
        self.service = service
        self.start, self.end = start, end
        self.user_id = user_id
        self.emit_record, self.emit_gap = emit_record, emit_gap
        self.seen = set()
        self.masked = set()

    def message(self, row, scope, prefix, title, link, **context):
        if row.get("messageType") != "message":
            return
        ident = prefix + "/" + _key(row)
        if ident in self.seen:
            return
        created = _timestamp(row.get("createdDateTime"))
        if created >= self.end:
            return
        edited = _timestamp(row["lastEditedDateTime"]) if row.get("lastEditedDateTime") else None
        if row.get("deletedDateTime") or (edited and edited >= self.end):
            had_activity = created >= self.start or (edited is not None and self.start <= edited < self.end)
            if had_activity and scope not in self.masked:
                self.emit_gap({"service": self.service, "scope": scope,
                               "reason": "An in-window message version is unavailable after an edit or deletion."})
                self.masked.add(scope)
            return
        stamp = edited or created
        if not self.start <= stamp < self.end:
            return
        self.seen.add(ident)
        author = row.get("from") or {}
        sender = author.get("user") or author.get("application") or {}
        own = bool(self.user_id and author.get("user") and sender.get("id") == self.user_id)
        direction = "chat" if self.service == "teams" else "channel"
        self.emit_record({
            "service": self.service, "id": ident, "time": _utc(stamp), "time_kind": "edited" if edited else "created",
            "title": title, "subject": _clean(row.get("subject")), "sender": _clean(sender.get("displayName")),
            "sender_id": _clean(sender.get("id")), "direction": "sent" if own else direction,
            "link": _link(row.get("webUrl"), "teams") or link, **_body(row), **context,
        })


def _teams(token, start, end, emit_record, emit_gap, user_id):
    evidence = _TeamsEvidence("teams", start, end, user_id, emit_record, emit_gap)
    seen_chats = set()
    # A later reaction advances lastModifiedDateTime without changing the body.
    # A server-side upper bound would hide valid messages in historical windows.
    # Filter create/edit times before examining content. Graph supports strict gt.
    lower = _utc(start - timedelta(milliseconds=1))
    params = {"$top": 50, "$orderby": "lastModifiedDateTime desc",
              "$filter": f"lastModifiedDateTime gt {lower}"}

    def read_chat(chat_id, chat):
        title = _chat_title(chat, user_id)
        link = _link(chat.get("webUrl"), "teams")
        url = _query("/me/chats/" + quote(chat_id, safe="") + "/messages", **params)
        for row in _pages(url, token, "teams"):
            evidence.message(row, "chat " + chat_id, chat_id, title, link, chat_id=chat_id)

    for chat in _pages(_query("/me/chats", **{"$top": 50, "$expand": "members"}), token, "teams"):
        chat_id = _key(chat)
        if chat_id not in seen_chats:
            seen_chats.add(chat_id)
            _with_gap("teams", "chat " + chat_id, lambda: read_chat(chat_id, chat), emit_gap)


def _channels(token, start, end, emit_record, emit_gap, user_id, channels):
    evidence = _TeamsEvidence("channels", start, end, user_id, emit_record, emit_gap)
    seen = set()

    def read_channel(channel):
        team, ident = channel["team_id"], channel["channel_id"]
        prefix = team + "/" + ident
        scope = "channel " + channel["title"] + " (" + ident + ")"
        path = f"/teams/{quote(team, safe='')}/channels/{quote(ident, safe='')}/messages"
        context = {"team_id": team, "channel_id": ident}

        def replies_for(post, parent):
            replies = post.get("replies")
            route = path + "/" + quote(parent, safe="") + "/replies"
            if replies is None:
                url = _query(route, **{"$top": 50})
            else:
                if not isinstance(replies, list):
                    raise ReadError("Graph returned an invalid list of replies")
                for reply in replies:
                    if not isinstance(reply, dict):
                        raise ReadError("Graph returned an unreadable reply")
                    yield reply
                url = post.get("replies@odata.nextLink")
            yield from _pages(url, token, "channels", expected_route=route)

        # Graph sorts entire chains and has no timestamp predicate here. Establish
        # descending order on complete chains; a root's timestamp alone cannot
        # bound the dates of its replies. Ignore uncertain timestamps for stopping.
        previous_latest = None
        can_stop_early = True
        url = _query(path, **{"$top": 10, "$expand": "replies"})
        for post in _pages(url, token, "channels", expected_route=path):
            parent = _key(post)
            evidence.message(post, scope, prefix, channel["title"], channel["link"], **context)
            latest = _timestamp(post["lastModifiedDateTime"]) if post.get("lastModifiedDateTime") else None
            try:
                for reply in replies_for(post, parent):
                    evidence.message(reply, scope, prefix + "/" + parent, channel["title"], channel["link"],
                                     reply_to_id=parent, **context)
                    if latest is not None:
                        modified = reply.get("lastModifiedDateTime")
                        latest = max(latest, _timestamp(modified)) if modified else None
            except ReadError as exc:
                emit_gap({"service": "channels", "scope": scope + " replies " + parent, "reason": str(exc)})
                latest = None
            if latest is not None and previous_latest is not None:
                if latest > previous_latest:
                    can_stop_early = False
                if can_stop_early and latest < previous_latest and latest < start:
                    break
            previous_latest = latest

    for item in channels or ():
        try:
            channel = parse_channel_link(item.get("link") if isinstance(item, dict) else None)
            if item.get("channel_id") != channel["channel_id"] or item.get("team_id") != channel["team_id"]:
                raise ValueError("Stored channel identifiers differ from the channel link. Run setup again.")
        except ValueError as exc:
            emit_gap({"service": "channels", "scope": "channel configuration", "reason": str(exc)})
            continue
        key = channel["team_id"], channel["channel_id"]
        if key not in seen:
            seen.add(key)
            _with_gap("channels", channel["title"], lambda: read_channel(channel), emit_gap)
    if not seen:
        emit_gap({"service": "channels", "scope": "project", "reason": "No valid Teams channels configured."})


def _mail(token, start, end, emit_record, emit_gap):
    seen_ids = set()
    seen_message_ids = set()
    fields = ("id,internetMessageId,conversationId,parentFolderId,subject,sender,from,"
              "receivedDateTime,sentDateTime,isDraft,uniqueBody,webLink")
    inbox = None
    try:
        inbox = _key(_get(_query("/me/mailFolders/inbox", **{"$select": "id"}), token, "outlook"))
    except ReadError as exc:
        emit_gap({"service": "outlook", "scope": "Inbox direction labels", "reason": str(exc)})

    def read_folder(path, field, is_sent):
        params = {"$select": fields, "$top": 50, "$orderby": field + " desc",
                  "$filter": f"{field} ge {_utc(start)} and {field} lt {_utc(end)}"}
        for row in _pages(_query(path, **params), token, "outlook"):
            if row.get("isDraft") is not False:
                continue
            ident = _key(row)
            message_id = _clean(row.get("internetMessageId"))
            stamp = _timestamp(row.get(field))
            if not start <= stamp < end or ident in seen_ids or (message_id and message_id in seen_message_ids):
                continue
            seen_ids.add(ident)
            if message_id:
                seen_message_ids.add(message_id)
            author = (row.get("sender") or row.get("from") or {}).get("emailAddress") or {}
            direction = "sent" if is_sent else "mailbox"
            if not is_sent and inbox and row.get("parentFolderId") == inbox:
                direction = "received"
            emit_record({
                "service": "outlook", "id": ident, "conversation_id": _clean(row.get("conversationId")),
                "time": _utc(stamp), "time_kind": field, "title": _clean(row.get("subject")),
                "sender": _clean(author.get("name") or author.get("address")), "direction": direction,
                "link": _link(row.get("webLink"), "outlook"), **_body(row),
            })

    # Prefer sent evidence for copies also found by mailbox-wide received time.
    _with_gap("outlook", "Sent Items",
              lambda: read_folder("/me/mailFolders/sentitems/messages", "sentDateTime", True), emit_gap)
    _with_gap("outlook", "Mailbox",
              lambda: read_folder("/me/messages", "receivedDateTime", False), emit_gap)


def collect(service, token, start_datetime, end_datetime, emit_record, emit_gap, *, user_id=None, channels=()):
    """Emit source records and coverage gaps for this account over [start, end).

    Teams includes delegated 1:1, group and meeting chats. Edited messages use
    the latest visible edit. The optional channels source reads posts and replies
    only in channels explicitly selected by link. Deleted versions are unavailable. Outlook covers the primary mailbox, including filed messages,
    and Sent Items. 'mailbox' marks copies of uncertain direction. Omit drafts,
    attachments and mail quoted in uniqueBody. Truncated excerpts are marked.
    """
    if service not in ("teams", "channels", "outlook"):
        raise ValueError("Expected teams, channels or outlook")
    if start_datetime.utcoffset() is None or end_datetime.utcoffset() is None:
        raise ValueError("Window bounds require timezone-aware timestamps")
    start = start_datetime.astimezone(timezone.utc)
    end = end_datetime.astimezone(timezone.utc)
    if start >= end:
        raise ValueError("Window start must precede end")
    try:
        if service == "teams":
            _teams(token, start, end, emit_record, emit_gap, user_id)
        elif service == "channels":
            _channels(token, start, end, emit_record, emit_gap, user_id, channels)
        else:
            _mail(token, start, end, emit_record, emit_gap)
    except (ReadError, ServiceUnavailable) as exc:
        emit_gap({"service": service, "scope": "account collection", "reason": str(exc)})
