"""Rolling digest windows and read-only evidence from the workspace repository."""

import os
import subprocess
from datetime import datetime, timedelta, timezone


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Expected a datetime with a timezone")
    return value.astimezone(timezone.utc)


def window(mode, count=None, end=None):
    """Return an inclusive UTC start and exclusive UTC end for a rolling window."""
    end = _utc(end) if end is not None else datetime.now(timezone.utc)
    presets = {"morning": 24, "evening": 9, "week": 168}
    if mode in presets:
        if count is not None:
            raise ValueError("Use days or hours to specify a custom window")
        hours = presets[mode]
    elif mode in ("days", "hours"):
        if isinstance(count, str) and count.isascii() and count.isdigit():
            count = int(count)
        if type(count) is not int or count < 1:
            raise ValueError("Custom days or hours must be a positive integer")
        hours = count * 24 if mode == "days" else count
    else:
        raise ValueError("Choose morning, evening, week, days or hours")
    try:
        return end - timedelta(hours=hours), end
    except OverflowError as exc:
        raise ValueError("The requested window exceeds the supported date range") from exc


GIT_SCOPE = "Commits reachable from local branches or the current HEAD, by committer time"


def _git(workspace, *args):
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(key, None)
    env.update(LC_ALL="C", GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="",
               GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1")
    return subprocess.run(
        ["git", "--no-pager", "-C", os.fspath(workspace), *args],
        env=env, stdin=subprocess.DEVNULL, capture_output=True, check=False,
    )


def collect_git(workspace, start, end, emit_record, emit_gap):
    """Emit one record per distinct reachable commit. No remote refresh or diff."""
    start, end = _utc(start), _utc(end)
    if start >= end:
        raise ValueError("The start must precede the end")
    summary = {"repository": None, "status": "unavailable", "count": 0, "scope": GIT_SCOPE}
    try:
        root = _git(workspace, "rev-parse", "--show-toplevel")
    except OSError:
        emit_gap("Git is unavailable for this workspace.")
        return summary
    if root.returncode:
        if b"not a git repository" in root.stderr:
            summary["status"] = "not_a_repository"
        else:
            emit_gap("Git could not inspect the workspace as a working tree.")
        return summary
    repository = os.fsdecode(root.stdout.removesuffix(b"\n"))
    summary["repository"] = repository

    identity = _git(workspace, "config", "--get", "user.email")
    email = identity.stdout.strip().lower() if identity.returncode == 0 else b""
    head = _git(workspace, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if head.returncode not in (0, 1):
        emit_gap("Git could not resolve the current HEAD.")
        return summary
    refs = ["--branches"]
    if head.returncode == 0:
        refs.append("HEAD")
    # --since (unlike --since-as-filter) can stop at an older child of a
    # recent commit, e.g. a branch with skewed or deliberately edited dates.
    log = _git(
        workspace, "log", "-z", "--no-color", "--no-notes", "--no-patch",
        "--no-decorate", "--no-show-signature", "--format=%H%x00%ct%x00%an%x00%ae%x00%P%x00%s",
        f"--since-as-filter=@{max(0, int(start.timestamp()))} +0000",
        f"--until=@{max(0, int(end.timestamp()))} +0000",
        *refs, "--",
    )
    if log.returncode:
        emit_gap("Git could not enumerate commit history. Check repository access and Git support for --since-as-filter.")
        return summary

    fields = log.stdout.split(b"\0")
    if fields.pop() or len(fields) % 6:
        emit_gap("Git returned incomplete commit metadata.")
        return summary
    for pos in range(0, len(fields), 6):
        sha, epoch, author, author_email, parents, subject = fields[pos:pos + 6]
        stamp = datetime.fromtimestamp(int(epoch), timezone.utc)
        if start <= stamp < end:
            emit_record({
                "source": "git",
                "repository": repository,
                "id": sha.decode("ascii"),
                "timestamp": stamp.isoformat(),
                "author": author.decode("utf-8", "replace"),
                "subject": subject.decode("utf-8", "replace"),
                "is_merge": len(parents.split()) > 1,
                "matches_git_identity": author_email.lower() == email if email else None,
            })
            summary["count"] += 1
    shallow = _git(workspace, "rev-parse", "--is-shallow-repository")
    if shallow.returncode or shallow.stdout.strip() != b"false":
        emit_gap("Git history may be incomplete at the clone's shallow boundary.")
        summary["status"] = "partial"
    else:
        summary["status"] = "ok"
    return summary
