"""Local source helper for the Codex stakeholder digest. CLI paths are caller-relative."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

from accounts import AccountError, AccountStore, AuthRequired
from graph_reader import AuthenticationRequired, collect as collect_graph, parse_channel_link
from local_sources import collect_git, window


SERVICES = ("teams", "outlook")
MICROSOFT_SOURCES = ("teams", "channels", "outlook")
LABEL = {"teams": "Teams", "channels": "Teams channels", "outlook": "Outlook"}


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError("Use an ISO 8601 timestamp with a UTC offset.") from None
    if parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("The timestamp needs a UTC offset.")
    return parsed.astimezone(timezone.utc)


def say(message):
    print(message, file=sys.stderr, flush=True)


def choose_accounts(store, services, filters):
    """Resolve nicknames only among bindings of the current project."""
    requested = {name.casefold() for name in filters}
    matches = []
    for service in services:
        if service in MICROSOFT_SOURCES:
            matches.extend((service, a) for a in store.bound(service)
                           if not requested or a.casefold() in requested)
    missing = requested.difference(alias.casefold() for _, alias in matches)
    return matches, sorted(missing)


def read_account(store, service, alias, start, end, interactive, write):
    """Retry a rejected token once silently and once after same-account browser login."""
    seen = set()
    field = {"source": service, "account": alias}
    gaps = set()

    def record(item):
        if item["id"] not in seen:
            seen.add(item["id"])
            write(dict(item, **field, kind="record"))

    def gap(item):
        # Stage gaps until the successful attempt, as a retry may close them.
        gaps.add((item["scope"], item["reason"]))

    def reconnect():
        if not interactive:
            raise AuthRequired("Sign-in required. Reconnect this account and resume.")
        say("Microsoft sign-in required for {} ({}). Opening your browser.".format(alias, LABEL[service]))
        store.reconnect(service, alias)

    try:
        signed_in = False
        for attempt in range(3):
            try:
                token = store.token(service, alias, force_refresh=(attempt == 1))
            except AuthRequired:
                if signed_in:
                    raise
                reconnect()
                signed_in = True
                token = store.token(service, alias)
            try:
                gaps.clear()
                options = {"user_id": store.user_id(service, alias)}
                if service == "channels":
                    options["channels"] = store.channels(alias)
                collect_graph(service, token, start, end, record, gap, **options)
                break
            except AuthenticationRequired:
                if signed_in or attempt == 2:
                    raise AuthRequired("Microsoft Graph still requires sign-in for this account.") from None
                if attempt == 1:
                    reconnect()
                    signed_in = True
    except (AccountError, KeyboardInterrupt) as error:
        message = "Sign-in canceled." if isinstance(error, KeyboardInterrupt) else str(error)
        gaps.add(("account", message))
    for scope, reason in sorted(gaps):
        write(dict(field, kind="gap", scope=scope, reason=reason))
    write(dict(field, kind="coverage", status="partial" if gaps else "ok", count=len(seen)))


@contextmanager
def evidence_sink(private_file):
    if not private_file:
        yield sys.stdout
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                     prefix="codex-digest-", suffix=".jsonl") as stream:
        try:
            yield stream
        except BaseException:
            Path(stream.name).unlink()
            raise
    print(json.dumps({"evidence_file": stream.name}))


def collect(args):
    end = args.end or datetime.now(timezone.utc)
    start, end = window(args.mode, args.count, end=end)
    if args.start is not None:
        start = args.start
    if start >= end:
        raise ValueError("The start must be earlier than the end.")
    services = list(dict.fromkeys(args.source)) or ["git", *MICROSOFT_SOURCES]
    if "teams" in services and "channels" not in services:
        services.insert(services.index("teams") + 1, "channels")
    with evidence_sink(args.private_file) as stream:
        def write(item):
            print(json.dumps(item, ensure_ascii=False), file=stream)

        write({"kind": "window", "start": start.isoformat(), "end": end.isoformat()})
        if "git" in services:
            def git_gap(reason):
                write({"kind": "gap", "source": "git", "reason": reason})
            summary = collect_git(args.workspace, start, end,
                                  lambda item: write(dict(item, kind="record")), git_gap)
            write(dict(summary, source="git", kind="coverage"))
        if any(s in services for s in MICROSOFT_SOURCES) or args.account:
            try:
                store = AccountStore(args.workspace)
                matches, missing = choose_accounts(store, services, args.account)
            except AccountError as error:
                write({"kind": "gap", "source": "microsoft", "reason": str(error)})
                return
            for alias in missing:
                write({"kind": "gap", "source": "microsoft", "account": alias,
                       "reason": "No matching account attached to this project for the selected sources. Use setup to attach it."})
            for service, alias in matches:
                read_account(store, service, alias, start, end, args.interactive, write)
            for service in MICROSOFT_SOURCES:
                if service in services and not any(s == service for s, _ in matches):
                    if service in args.source and not args.account:
                        write({"kind": "gap", "source": service,
                               "reason": "This requested source has no selection in the project. Use setup to enable it."})
                    write({"kind": "coverage", "source": service, "status": "no_selected_account"})


class NextService(Exception):
    pass


def answer(prompt):
    try:
        value = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise NextService() from None
    if value.casefold() in {"cancel", "done"}:
        raise NextService()
    return value


def wizard_channels(store, alias):
    try:
        if answer("Configure channel posts for {}? [y/N] ".format(alias)).casefold() not in {"y", "yes"}:
            return
        print("Use Teams' Copy link to channel. Adding the first channel requests ChannelMessage.Read.All.")
        while True:
            print("Selected channels:", ", ".join(c["title"] for c in store.channels(alias)) or "(none)")
            link = answer("Channel link to add (-link to remove, Enter or Cancel to finish channels): ")
            if not link:
                return
            remove = link.startswith("-")
            try:
                channel = parse_channel_link(link[1:].strip() if remove else link)
                if remove:
                    store.remove_channel(alias, channel["channel_id"])
                else:
                    store.add_channel(alias, channel)
            except (AccountError, ValueError) as error:
                say(str(error))
    except (NextService, KeyboardInterrupt):
        return


def wizard(store):
    print("Project:", store.project)
    client = os.environ.get("DIGEST_MICROSOFT_CLIENT_ID", "")
    tenant = os.environ.get("DIGEST_MICROSOFT_TENANT", "organizations")
    for service in SERVICES:
        title = LABEL[service]
        try:
            print("Attached {} accounts: {}".format(title, ", ".join(store.bound(service)) or "(none)"))
            if answer("Configure {}? [y/N] ".format(title)).casefold() not in {"y", "yes"}:
                continue
            while True:
                saved = store.available(service)
                print("Saved {} nicknames: {}".format(title, ", ".join(saved) or "(none)"))
                alias = answer("Nickname to attach or add (-name to detach, Enter or Cancel to continue): ")
                if not alias:
                    break
                try:
                    if alias.startswith("-"):
                        store.unbind(service, alias[1:].strip())
                    elif alias.casefold() in {a.casefold() for a in saved}:
                        store.bind(service, alias)
                    else:
                        print("Use your Entra desktop application (client) ID. Microsoft sign-in opens in your browser.")
                        selected = answer("Application ID{}: ".format(" [" + client + "]" if client else "")) or client
                        directory = answer("Directory (tenant) ID or authority [{}]: ".format(tenant)) or tenant
                        store.connect(service, alias, selected, directory)
                        client, tenant = selected, directory
                    print("Attached:", ", ".join(store.bound(service)) or "(none)")
                    if service == "teams" and not alias.startswith("-"):
                        wizard_channels(store, alias)
                except AccountError as error:
                    say(str(error))
        except (NextService, KeyboardInterrupt):
            continue
    for service in SERVICES:
        print("{}: {}".format(LABEL[service], ", ".join(store.bound(service)) or "(none)"))


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".", help="Project folder used for Git and account selection")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Interactive Teams and Outlook account wizard")
    commands.add_parser("accounts", help="List project bindings and reusable nicknames")
    for name in ("bind", "unbind", "connect", "reconnect"):
        p = commands.add_parser(name)
        p.add_argument("service", choices=MICROSOFT_SOURCES if name == "reconnect" else SERVICES)
        p.add_argument("alias")
        if name == "connect":
            p.add_argument("--client-id", default=os.environ.get("DIGEST_MICROSOFT_CLIENT_ID"))
            p.add_argument("--tenant", default=os.environ.get("DIGEST_MICROSOFT_TENANT", "organizations"))
    for name in ("channels", "channel-add", "channel-remove"):
        p = commands.add_parser(name, help="Manage selected channel links for a project Teams nickname")
        p.add_argument("alias")
        if name != "channels":
            p.add_argument("link")
    p = commands.add_parser("collect", help="Emit time-bounded supplementary evidence as JSON lines")
    p.add_argument("mode", choices=("week", "morning", "evening", "days", "hours"), default="week", nargs="?")
    p.add_argument("count", type=int, nargs="?")
    p.add_argument("--end", type=timestamp, help="Frozen reporting cutoff")
    p.add_argument("--start", type=timestamp, help="Explicit inclusive lower bound for calendar/date ranges")
    p.add_argument("--source", choices=("git", *MICROSOFT_SOURCES), action="append", default=[])
    p.add_argument("--account", action="append", default=[], help="Restrict project bindings by nickname")
    p.add_argument("--interactive", action="store_true", help="Open Microsoft sign-in when silent renewal fails")
    p.add_argument("--private-file", action="store_true", help="Emit only the path to a private temporary JSONL file")
    args = parser.parse_args()
    try:
        if args.command == "collect":
            collect(args)
            return
        store = AccountStore(args.workspace)
        if args.command == "setup":
            wizard(store)
        elif args.command == "accounts":
            print(json.dumps({"project": store.project, "services": {
                s: {"attached": store.bound(s), "available": store.available(s)} for s in SERVICES},
                "channels": {a: store.channels(a) for a in store.bound("teams")}}))
        elif args.command == "channels":
            print(json.dumps(store.channels(args.alias)))
        elif args.command in ("channel-add", "channel-remove"):
            channel = parse_channel_link(args.link)
            if args.command == "channel-add":
                store.add_channel(args.alias, channel)
            else:
                store.remove_channel(args.alias, channel["channel_id"])
        elif args.command == "connect":
            if not args.client_id:
                raise ValueError("Provide the public Entra application ID using --client-id.")
            store.connect(args.service, args.alias, args.client_id, args.tenant)
        else:
            getattr(store, args.command)(args.service, args.alias)
    except (AccountError, ValueError, OverflowError) as error:
        parser.exit(2, "{}\n".format(error))


if __name__ == "__main__":
    cli()
