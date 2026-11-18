# Morning briefing

Invocation in Codex: `$codex-stakeholder-digest morning`. This is a manual chat command; produce the briefing when invoked. Use the shared history-access and evidence rules, with the overrides below.

## Use recent evidence only

- Default to the rolling **24 hours ending when the request was received**. State the exact window and the local date meant by “today,” using the user's timezone. An explicit time range or request for the previous calendar day overrides the rolling window; calendar-day boundaries follow the user's timezone, including daylight-saving changes.
- Cover accessible projects unless the user narrows the scope. Include older, pinned, and archived chats with activity in the window; do not filter on chat creation dates.
- Enumerate metadata as needed, but restrict substantive message and tool-result extraction to the selected window before analysis. Prefer timestamp-filtered local reads when app tools cannot bound retrieval. Ignore older records incidentally returned on a boundary page. **Do not fetch earlier turns, load prior digests, or reconstruct a historical backlog to fill gaps.** If recent evidence lacks context, qualify or omit the claim.
- Treat earlier events quoted in a recent message as background, not newly completed work. If the rolling window includes activity from this morning, label that activity “This morning” rather than attributing it to yesterday. Resolve “today” and “tomorrow” relative to the source message's local date.

## Select useful work and likely focus

For **What I did yesterday**, include delivered outcomes, substantial progress, decisions, meaningful investigations, useful findings, and significant blockers encountered. Describe the user's work in an easy-to-reuse style, while attributing teammates' contributions accurately. A request alone is not an accomplishment. Preserve distinctions such as drafted versus sent, implemented versus deployed, and started versus completed.

For **My focus today**, prioritize explicit plans or commitments for today's local date. Then infer likely priorities from unfinished active work, requested reviews, immediate next steps, and dependencies that matter to that work. Mark each focus item **Planned** when explicitly supported or **Likely focus** when inferred. Give the brief evidence-based reason for an inference when it is not apparent. State a known blocker or dependency alongside the action; do not assign another person's work to the user.

Reconcile later completions, cancellations, deferrals, and priority changes within the window. Do not turn every open issue into today's task, repeat resolved blockers as priorities, invent commitments, or pull next week's plans into today without evidence of an immediate action. Research or an assistant suggestion alone does not establish the user's plan. Omit speculative busywork and generic productivity advice. If no defensible focus can be inferred, say that the recent chats do not establish one; do not fill the gap using calendars or other external sources.

## Return two main sections

Open with one short line giving the window, timezone, and material coverage gaps, then use exactly these two main sections:

1. **What I did yesterday (last 24 hours)** — adapt the parenthetical if the user chose a different window.
2. **My focus today** — identify today's local date if it is not clear from the opening line.

Within each section, group concise bullets under short topic/project labels. Put the most important topics and actions first. Combine related implementation, testing, and review details into a useful outcome instead of listing each operation. Today should normally contain fewer bullets than yesterday.

Aim for roughly **8–15 substantive bullets across both sections** on a busy day. This is guidance, not a minimum or a hard cutoff: use fewer on a quiet day and modestly more when important work warrants it. Favor inclusion of useful developments, but merge overlaps and drop low-value details before expanding the list. Keep each bullet to one or two short sentences; do not add an exhaustive appendix.

Reuse compact source markers and a short source footer; a topic-level citation may support multiple bullets only when it supports all of them. Keep the two content sections dominant. Distinguish no material recent activity from unavailable history, preserve the two-section structure even on a quiet day, and do not invent either accomplishments or priorities to fill it.
