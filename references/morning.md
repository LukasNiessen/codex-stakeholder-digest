# Morning briefing

Invocation in Codex: `$codex-stakeholder-digest morning`. This is a manual chat command; produce the briefing when invoked. Use the shared history-access and evidence rules, with the overrides below.

## Use recent evidence only

- Default to the rolling **24 hours ending when the request was received**. State the exact window and the local date meant by “today,” using the user's timezone. An explicit time range or request for the previous calendar day overrides the rolling window; calendar-day boundaries follow the user's timezone, including daylight-saving changes.
- Cover accessible projects unless the user narrows the scope. Include older, pinned, and archived chats with activity in the window; do not filter on chat creation dates.
- Enumerate metadata as needed, but restrict substantive message and tool-result extraction to the selected window before analysis. Prefer timestamp-filtered local reads when app tools cannot bound retrieval. Ignore older records incidentally returned on a boundary page. **Do not fetch earlier turns, load prior digests, or reconstruct a historical backlog to fill gaps.** If recent evidence lacks context, qualify or omit the claim.
- Treat earlier events quoted in a recent message as background, not newly completed work. If the rolling window includes activity from this morning, label that activity “This morning” rather than attributing it to yesterday. Resolve “today” and “tomorrow” relative to the source message's local date.

## Select useful work and likely focus

For **What I did yesterday**, include delivered outcomes, substantial progress, decisions, meaningful investigations, useful findings, and significant blockers encountered. Describe the user's work in an easy-to-reuse style, while attributing teammates' contributions accurately. A request alone is not an accomplishment. Preserve distinctions such as drafted versus sent, implemented versus deployed, and started versus completed.

For **My focus today**, prioritize explicit plans or commitments for today's local date. Then infer likely priorities from unfinished active work, requested reviews, immediate next steps, and dependencies that matter to that work. Mark each focus item **Planned** when explicitly supported or **Likely focus** when inferred. Preserve stated timing; do not add a time of day or deadline. Give the brief evidence-based reason for an inference when it is not apparent. State a known blocker or dependency alongside the action; do not assign another person's work to the user.

Reconcile later completions, cancellations, deferrals, and priority changes within the window. Do not turn every open issue into today's task, repeat resolved blockers as priorities, invent commitments, or pull next week's plans into today without evidence of an immediate action. Research or an assistant suggestion alone does not establish the user's plan. Omit speculative busywork and generic productivity advice. If no defensible focus can be inferred, say that the recent chats do not establish one; do not fill the gap using calendars or other external sources.

## Surface input needs and blockers

For **Input needed from me**, surface unresolved questions, decisions, approvals, missing information, or material ambiguities that call for the user's response. State the specific input needed and which work or decision it affects; include options only when supported by the evidence. Clearly label inferred clarification needs. Do not turn every unknown into a question for the user or assign someone else's decision to them. Present these as briefing items rather than interrupting the report to ask the user or solve the issue.

For **Blockers**, describe current conditions actually preventing or materially delaying progress, the affected work, and the known dependency/owner or next unblocking action. An external dependency, risk, or unresolved issue is not automatically a blocker. Qualify suspected blockers and unknown ownership instead of inventing certainty, deadlines, or responsibility. Exclude conditions resolved or superseded later in the window; a material resolution may belong under yesterday's work.

If a question or blocker is tightly tied to one bullet in another section, add **Input needed:** or **Blocked by:** there when that reads more clearly. Use the dedicated sections for standalone or cross-topic items. Give each item one primary home; do not repeat the same approval, uncertainty, or dependency under focus, input, and blockers. When user input is itself blocking work, describe both the request and blocking consequence together.

## Return the morning briefing

Open with one short line giving the window, timezone, and material coverage gaps, then organize the briefing in this order:

1. **What I did yesterday (last 24 hours)** — adapt the parenthetical if the user chose a different window.
2. **My focus today** — identify today's local date if it is not clear from the opening line.
3. **Input needed from me** — unresolved decisions, clarifications, approvals, or information requests.
4. **Blockers** — current impediments and what is needed to unblock them.

Within each section, group concise bullets under short topic/project labels. Put the most important topics and actions first. Combine related implementation, testing, and review details into a useful outcome instead of listing each operation. Today should normally contain fewer bullets than yesterday. If input needs or blockers have no standalone items after inline placement, omit those empty sections or briefly say none were identified in the reviewed chats; missing access must not be presented as proof that none exist.

Aim for roughly **8–15 substantive bullets across the entire briefing** on a busy day, including input needs and blockers. This is guidance, not a minimum or a hard cutoff: use fewer on a quiet day and modestly more when important work warrants it. Favor inclusion of useful developments, but merge overlaps and drop low-value details before expanding the list. Keep each bullet to one or two short sentences; do not add an exhaustive appendix.

Reuse compact source markers and a short source footer; a topic-level citation may support multiple bullets only when it supports all of them. Keep sources subordinate to the briefing. Distinguish no material recent activity from unavailable history, retain the yesterday/today sections even on a quiet day, and do not invent accomplishments, priorities, questions, or blockers to fill the report.
