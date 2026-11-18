# Accessing Codex chat history

Use this reference when gathering evidence. The app tool route and local storage shapes below were checked on 2026-11-16. Discover current tool signatures and inspect current schemas; local formats are implementation details and may change.

## Prefer available app tools

Discover tools by capability; the namespace may differ between environments. This Codex desktop environment provides:

- `mcp__codex_app__list_threads({limit})`: `pinnedThreads` and non-pinned `threads`, with IDs, kinds, host IDs, project context, titles, and recency. Filter for `kind: "codex"`; the same response can include ChatGPT chats. Inspect `unavailableHosts` and `unavailableSources`.
- `mcp__codex_app__list_archived_threads({source: "codex", hostId?, limit, cursor?})`: a separate archived list. Follow `nextCursor`; use the relevant returned host IDs when multiple hosts are available. Do not unarchive chats to read them.
- `mcp__codex_app__read_thread({threadId, hostId?, turnLimit, cursor?, includeOutputs?, maxOutputCharsPerItem?})`: recent turns with timestamps, messages, and tool activity. Follow `page.nextCursor` for older turns. Request tool outputs or larger text limits when evidence is truncated. Preserve the title verbatim in citations.

The tested `list_threads` and `list_archived_threads` tools accept at most `limit: 50`. Only the archived listing provides a cursor. A full or silently capped non-archived result is not proof that all chats were enumerated; use local indexes to close local coverage gaps. Pinned entries are not in chronological order and must be considered separately. Do not assume archived results are sorted by activity without verifying it. Local files cannot close gaps for an unavailable remote host.

In stakeholder-digest mode, read turns back through the start of the window and enough preceding context to interpret them. In morning mode, use only content inside its selected window: prefer timestamp-filtered local reads when app tools cannot bound retrieval, ignore out-of-window records returned on a boundary page, and do not fetch older context. For historical windows, keep paging past newer turns. Inspect turns spanning a boundary and use item timestamps when available. Do not stop at the latest assistant answer if earlier in-window activity could contain other material developments.

## Local fallback or completeness check

Use `$CODEX_HOME` if set, otherwise `~/.codex`. Inspect only history-related stores; account credentials and authentication files are unnecessary. Open SQLite databases with a read-only URI (`mode=ro`), inspect `sqlite_master` and `PRAGMA table_info`, and select needed columns rather than dumping entire databases.

Observed sources:

- `state_*.sqlite`: a `threads` table with `id`, `title`/`name`, `cwd`, `project_id`, `rollout_path`, `created_at`, `updated_at`, `archived`, `source`, `agent_path`, and `history_mode` among other fields. Thread/spawn relationships can help deduplicate delegated work. Inspect timestamps and source fields before filtering.
- `thread_history_*.sqlite`: normalized `thread_turns` (`thread_id`, `turn_id`, `started_at`, `completed_at`, status) and `thread_items` (`thread_id`, `turn_id`, `item_id`, `created_at_ms`, `started_at_ms`, `completed_at_ms`, `item_type`, `item_json`). These support discovering old chats with recent items and reading their content. Inspect actual `item_json` shapes before extracting text.
- `session_index.jsonl`: compact discovery metadata such as `id`, `thread_name`, and `updated_at`; not full conversation evidence.
- `sessions/**/*.jsonl` and `archived_sessions/**/*.jsonl`: rollout histories. Prefer indexed `rollout_path` values. If an index is missing or incomplete, inspect these locations; a file's directory date usually reflects creation and must not exclude an older session with recent activity.

Enumerate using available indexes, then confirm the requested window against actual item/turn timestamps. Check timestamp units: `_ms` values are milliseconds, other observed time columns use epoch seconds. Metadata updates can occur without substantive chat activity. Missing files, stale projections, unsupported schemas, malformed records, and inaccessible stores are coverage gaps to resolve where possible or disclose.

Rollout records have a timestamp, type, and payload. The tested paginated format includes `event_msg` payloads of type `item_completed` containing a structured `item`, plus `response_item` messages/tool results. Other versions may use `user_message` and `agent_message` events. Extract user messages, visible assistant messages, and relevant tool results; do not extract private reasoning or encrypted content. Deduplicate mirrored events and items by their IDs, and avoid counting inherited fork history twice. A compaction summary is useful context but is not a replacement for accessible original evidence.

Read bounded batches while maintaining a coverage/evidence ledger. If tool output is truncated, narrow queries or persist temporary extracts in the workspace and continue reading; do not quietly treat truncation as the end of the data. Keep the source stores unchanged.

## Official API context

The [Codex app-server documentation](https://learn.chatgpt.com/docs/app-server) documents paginated `thread/list`, `thread/turns/list`, and `thread/items/list` reads. `thread/list` defaults to creation-time ordering and excludes archives unless `archived: true` is requested. These RPC methods are not the same interface as the desktop tools above; use them only through an available, configured client. Do not invent an HTTP endpoint, start another daemon, or resume conversations just to read their history.
