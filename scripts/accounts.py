"""Project bindings and OS-protected delegated Microsoft sessions for the digest."""
import hashlib
import os
import re
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import UUID

from local_sources import _git


SCOPES = {"teams": "Chat.Read", "outlook": "Mail.Read", "channels": "ChannelMessage.Read.All"}


class AccountError(Exception):
    """Safe to display. Never include tokens, raw HTTP responses or browser URLs."""


class AuthRequired(AccountError):
    """Continuing with this account requires a browser sign-in."""


def _project_key(directory):
    directory = Path(directory).resolve()
    try:
        result = _git(directory, "rev-parse", "--git-common-dir")
    except OSError:
        return str(directory)
    if result.returncode:
        return str(directory)
    return str((directory / os.fsdecode(result.stdout.removesuffix(b"\n"))).resolve())


def _nickname(alias):
    name = alias.strip()
    if not name or len(name) > 80 or not name.isprintable():
        raise AccountError("Enter a printable account nickname of 1 to 80 characters.")
    return name.casefold()


def _scope(service):
    if service not in SCOPES:
        raise AccountError("Choose Teams or Outlook.")
    return SCOPES[service]


def _directory(tenant):
    tenant = tenant.strip().lower()
    if tenant in {"organizations", "common", "consumers"}:
        return tenant
    try:
        return str(UUID(tenant))
    except ValueError:
        if re.fullmatch(r"(?:[a-z0-9][a-z0-9-]*\.)+[a-z0-9][a-z0-9-]*", tenant):
            return tenant
        raise AccountError("Enter the Entra directory ID, tenant domain, common, consumers or organizations.")


def _msal_cache(location):
    try:
        import msal
        from msal_extensions import build_encrypted_persistence
        from msal_extensions.persistence import PersistenceNotFound
    except ImportError:
        raise AccountError("Install scripts/requirements-microsoft.txt to connect Microsoft accounts.") from None
    try:
        store = build_encrypted_persistence(str(location))
        if not store.is_encrypted:
            raise ValueError()
    except Exception:
        raise AccountError("The operating system's protected credential store is unavailable.") from None
    return msal, store, PersistenceNotFound


def _app(msal, client, tenant, cache):
    return msal.PublicClientApplication(
        client_id=client, authority="https://login.microsoftonline.com/" + tenant, token_cache=cache,
        timeout=20,
    )


def _check_result(result, scope):
    if not result or result.get("error") in {
        "invalid_grant", "interaction_required", "login_required", "consent_required",
        "account_selection_required", "no_tokens_found",
    }:
        raise AuthRequired("Microsoft sign-in is required for this account.")
    if not result.get("access_token"):
        # Only standardized error identifiers and numeric Entra error codes may leave this module.
        code = str(result.get("error", "authentication_failed"))
        if not re.fullmatch("[a-z_]{1,50}", code):
            code = "authentication_failed"
        numbers = [str(n) for n in (result.get("error_codes") or []) if isinstance(n, int)]
        detail = " " + ", ".join(numbers[:2]) if numbers else ""
        raise AccountError(f"Microsoft sign-in returned {code}{detail}.")
    granted = result.get("scope")
    if granted is not None and scope.casefold() not in {
        item.rsplit("/", 1)[-1].casefold() for item in granted.split()
    }:
        raise AuthRequired(f"Microsoft has not granted delegated {scope} access.")


@contextmanager
def _auth_errors():
    try:
        yield
    except AccountError:
        raise
    except Exception:
        # MSAL and keyring exceptions can carry raw request/response data.
        raise AccountError("Microsoft sign-in or protected storage failed. Check connectivity, the app registration and credential store.") from None


class AccountStore:
    def __init__(self, project_dir):
        self.project = _project_key(project_dir)
        base = Path(os.environ.get("XDG_CONFIG_HOME", ""))
        if not base.is_absolute():
            base = Path.home() / ".config"
        self.directory = base.resolve() / "codex-stakeholder-digest"
        self.db = self.directory / "accounts.sqlite3"

    @contextmanager
    def _connection(self, write=False):
        try:
            if not write and (not self.db.exists() or self.db.stat().st_size == 0):
                yield None
                return
            if write:
                self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                os.close(os.open(self.db, os.O_CREAT | os.O_RDWR, 0o600))
                connection = sqlite3.connect(self.db, timeout=330, isolation_level=None)
            else:
                connection = sqlite3.connect(self.db.as_uri() + "?mode=ro", uri=True, timeout=330)
            with closing(connection):
                connection.row_factory = sqlite3.Row
                if write:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("""CREATE TABLE IF NOT EXISTS accounts (
                        service TEXT, key TEXT, name TEXT, client TEXT, tenant TEXT, oid TEXT,
                        PRIMARY KEY (service, key))""")
                    connection.execute("""CREATE TABLE IF NOT EXISTS bindings (
                        project TEXT, service TEXT, key TEXT, PRIMARY KEY (project, service, key))""")
                    connection.execute("""CREATE TABLE IF NOT EXISTS project_channels (
                        project TEXT, key TEXT, channel_id TEXT, team_id TEXT, title TEXT, link TEXT, tenant_id TEXT,
                        PRIMARY KEY (project, key, channel_id))""")
                    connection.commit()  # A canceled first login still leaves a readable, empty database.
                    # Also serialize read-modify-write of MSAL caches, including refresh-token rotation.
                    connection.execute("BEGIN IMMEDIATE")
                yield connection
                if write:
                    connection.commit()
        except (OSError, sqlite3.Error):
            raise AccountError("Cannot access the digest's local account configuration.") from None

    def _names(self, service, bound):
        _scope(service)
        with self._connection() as con:
            if con is None:
                return []
            query = "SELECT name FROM accounts WHERE service = ?"
            args = [service]
            if bound:
                query += " AND key IN (SELECT key FROM bindings WHERE project = ? AND service = ?)"
                args.extend([self.project, service])
            return [row["name"] for row in con.execute(query + " ORDER BY key", args)]

    def available(self, service):
        return self._names(service, False)

    def bound(self, service):
        return self._names(service, True)

    def _row(self, con, service, key, *, require_binding):
        _scope(service)
        if con is None:
            raise AccountError("Unknown account nickname for this service.")
        row = con.execute("SELECT * FROM accounts WHERE service = ? AND key = ?", (service, key)).fetchone()
        if row is None:
            raise AccountError("Unknown account nickname for this service.")
        if require_binding and not con.execute(
            "SELECT 1 FROM bindings WHERE project = ? AND service = ? AND key = ?",
            (self.project, service, key),
        ).fetchone():
            raise AccountError("This account is not enabled for this project.")
        return row

    def _bind(self, con, service, key):
        con.execute("INSERT OR IGNORE INTO bindings VALUES (?, ?, ?)", (self.project, service, key))

    def bind(self, service, alias):
        if service == "channels":
            raise AccountError("Select a channel under an attached Teams account.")
        key = _nickname(alias)
        with self._connection(write=True) as con:
            self._row(con, service, key, require_binding=False)
            self._bind(con, service, key)

    def unbind(self, service, alias):
        _scope(service)
        key = _nickname(alias)
        with self._connection(write=True) as con:
            con.execute("DELETE FROM bindings WHERE project = ? AND service = ? AND key = ?",
                        (self.project, service, key))
            if service in ("teams", "channels"):
                con.execute("DELETE FROM project_channels WHERE project = ? AND key = ?", (self.project, key))
                con.execute("DELETE FROM bindings WHERE project = ? AND service = 'channels' AND key = ?",
                            (self.project, key))

    def channels(self, alias):
        key = _nickname(alias)
        with self._connection() as con:
            # Older configurations have neither channel bindings nor a project_channels table.
            if con is None or not con.execute(
                "SELECT 1 FROM bindings WHERE project = ? AND key = ? AND service = 'channels'",
                (self.project, key),
            ).fetchone():
                return []
            rows = con.execute("""SELECT team_id, channel_id, title, link, tenant_id FROM project_channels
                WHERE project = ? AND key = ? ORDER BY title, channel_id""", (self.project, key))
            return [dict(row) for row in rows]

    def add_channel(self, alias, channel):
        key = _nickname(alias)
        with self._connection(write=True) as con:
            teams = self._row(con, "teams", key, require_binding=True)
            tenant = channel.get("tenant_id")
            if tenant and tenant.lower() != teams["tenant"]:
                raise AccountError("This channel link belongs to another directory. Select its Teams account.")
            existing = con.execute("SELECT * FROM accounts WHERE service = 'channels' AND key = ?", (key,)).fetchone()
            if existing:
                try:
                    self._silent(existing, False)
                except AuthRequired:
                    self._sign_in("channels", key, teams["client"], teams["tenant"], teams)
            else:
                self._sign_in("channels", key, teams["client"], teams["tenant"], teams)
                con.execute("INSERT INTO accounts VALUES ('channels', ?, ?, ?, ?, ?)",
                            (key, teams["name"], teams["client"], teams["tenant"], teams["oid"]))
            con.execute("INSERT OR REPLACE INTO project_channels VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (self.project, key, channel["channel_id"], channel["team_id"], channel["title"],
                         channel["link"], tenant))
            self._bind(con, "channels", key)

    def remove_channel(self, alias, channel_id):
        key = _nickname(alias)
        with self._connection(write=True) as con:
            con.execute("DELETE FROM project_channels WHERE project = ? AND key = ? AND channel_id = ?",
                        (self.project, key, channel_id))
            con.execute("""DELETE FROM bindings WHERE project = ? AND key = ? AND service = 'channels'
                AND NOT EXISTS (SELECT 1 FROM project_channels WHERE project = ? AND key = ?)""",
                        (self.project, key, self.project, key))

    def user_id(self, service, alias):
        with self._connection() as con:
            return self._row(con, service, _nickname(alias), require_binding=True)["oid"]

    def _session(self, service, key):
        digest = hashlib.sha256((service + "/" + key).encode("utf-8")).hexdigest()
        return _msal_cache(self.directory / ("session-" + digest))

    def _sign_in(self, service, key, client, tenant, previous):
        # A fresh in-memory cache prevents signing into the wrong account from replacing a saved session.
        scope = _scope(service)
        with _auth_errors():
            msal, persistence, _ = self._session(service, key)
            cache = msal.SerializableTokenCache()
            app = _app(msal, client, tenant, cache)
            result = app.acquire_token_interactive(scopes=[scope], prompt="select_account", timeout=300)
            _check_result(result, scope)
            claims = result.get("id_token_claims") or {}
            try:
                tenant_id, oid = (str(UUID(claims[field])) for field in ("tid", "oid"))
            except (KeyError, TypeError, ValueError, AttributeError):
                raise AccountError("Microsoft did not identify the signed-in account and directory.") from None
            if previous is not None and (tenant_id, oid) != (previous["tenant"], previous["oid"]):
                raise AccountError("The sign-in used another account or directory. Select the original account or use a new nickname.")
            persistence.save(cache.serialize())
            return tenant_id, oid, result["access_token"]

    def connect(self, service, alias, client_id, tenant="organizations"):
        if service == "channels":
            raise AccountError("Select a channel under an attached Teams account.")
        _scope(service)
        key = _nickname(alias)
        try:
            client = str(UUID(client_id.strip()))
        except ValueError:
            raise AccountError("Enter the application's public client ID as a UUID.") from None
        tenant = _directory(tenant)
        with self._connection(write=True) as con:
            previous = con.execute("SELECT * FROM accounts WHERE service = ? AND key = ?", (service, key)).fetchone()
            if previous and previous["client"] != client:
                raise AccountError("This nickname uses another app registration. Use a different nickname.")
            actual_tenant, oid, _ = self._sign_in(service, key, client, tenant, previous)
            con.execute("INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?, ?, ?)",
                        (service, key, alias.strip(), client, actual_tenant, oid))
            self._bind(con, service, key)

    def reconnect(self, service, alias):
        key = _nickname(alias)
        with self._connection(write=True) as con:
            row = self._row(con, service, key, require_binding=True)
            self._sign_in(service, key, row["client"], row["tenant"], row)

    def _silent(self, row, force_refresh):
        scope = _scope(row["service"])
        with _auth_errors():
            msal, persistence, missing = self._session(row["service"], row["key"])
            cache = msal.SerializableTokenCache()
            try:
                cache.deserialize(persistence.load())
            except missing:
                raise AuthRequired("The saved sign-in was removed. Reconnect this account.") from None
            app = _app(msal, row["client"], row["tenant"], cache)
            # Each cache holds one signed-in identity. MSAL may record a discovery alias
            # (e.g. "common") as its realm. Pin the API authority to the verified tid
            # above and select using the resource-tenant oid, including for guests.
            matches = app.get_accounts()
            if len(matches) != 1 or (matches[0].get("local_account_id") or "").lower() != row["oid"]:
                raise AuthRequired("Reconnect to verify the original Microsoft account and directory.")
            result = app.acquire_token_silent_with_error(
                [scope], account=matches[0], force_refresh=force_refresh,
            )
            _check_result(result, scope)
            claims = result.get("id_token_claims")
            expected = (row["tenant"], row["oid"])
            if claims and ((claims.get("tid") or "").lower(), (claims.get("oid") or "").lower()) != expected:
                raise AuthRequired("Reconnect to verify the original Microsoft account and directory.")
            if cache.has_state_changed:
                persistence.save(cache.serialize())
            return result["access_token"]

    def token(self, service, alias, *, interactive=False, force_refresh=False):
        key = _nickname(alias)
        with self._connection(write=True) as con:
            row = self._row(con, service, key, require_binding=True)
            try:
                return self._silent(row, force_refresh)
            except AuthRequired:
                if not interactive:
                    raise
            return self._sign_in(service, key, row["client"], row["tenant"], row)[2]
