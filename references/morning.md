# Morning briefing

Invocation in Codex: `$codex-stakeholder-digest morning`. This is a manual chat command; produce the briefing when invoked. Use the shared history-access and evidence rules, with the overrides below.

## Use recent evidence only

- Default to the rolling **24 hours ending when the request was received**. Compute the exact window and the local date meant by “today” using the user's timezone. Keep retrieval details out of the opening: display only the briefing date unless the user asks for the precise window. An explicit time range or request for the previous calendar day overrides the rolling window; calendar-day boundaries follow the user's timezone, including daylight-saving changes.
- Cover accessible projects unless the user narrows the scope. Include older, pinned, and archived chats with activity in the window; do not filter on chat creation dates.
- Enumerate metadata as needed, but restrict substantive message and tool-result extraction to the selected window before analysis. Prefer timestamp-filtered local reads when app tools cannot bound retrieval. Ignore older records incidentally returned on a boundary page. **Do not fetch earlier turns, load prior digests, or reconstruct a historical backlog to fill gaps.** If recent evidence lacks context, qualify or omit the claim.
- Treat earlier events quoted in a recent message as background, not newly completed work. If the window includes activity from today, label it briefly with “Today so far” or “Overnight,” as appropriate to the source time. Do not attribute it to yesterday or call shortly-after-midnight activity “This morning.” Resolve “today” and “tomorrow” relative to the source message's local date.

## Select useful work and likely focus

For **What I did yesterday**, include delivered outcomes, substantial progress, decisions, meaningful investigations, useful findings, and significant blockers encountered. Describe the user's work in an easy-to-reuse style, while attributing teammates' contributions accurately. A request alone is not an accomplishment. Preserve distinctions such as drafted versus sent, implemented versus deployed, and started versus completed.

For **My focus today**, prioritize explicit plans or commitments for today's local date. Then infer likely priorities from unfinished active work, requested reviews, immediate next steps, and dependencies that matter to that work. Mark each focus item with a compact **Planned** or **Likely** label. Preserve stated timing; do not add a time of day or deadline. Give the evidence-based reason for an inference only when needed, as a short sub-bullet rather than a justification sentence appended to every item. State a known blocker or dependency alongside the action; do not assign another person's work to the user.

Reconcile later completions, cancellations, deferrals, and priority changes within the window. Do not turn every open issue into today's task, repeat resolved blockers as priorities, invent commitments, or pull next week's plans into today without evidence of an immediate action. Research or an assistant suggestion alone does not establish the user's plan. Omit speculative busywork and generic productivity advice. If no defensible focus can be inferred, say that the recent chats do not establish one; do not fill the gap using calendars or other external sources.

## Surface input needs and blockers

For **Input needed from me**, surface unresolved questions, decisions, approvals, missing information, or material ambiguities that call for the user's response. State the specific input needed and which work or decision it affects; include options only when supported by the evidence. Clearly label inferred clarification needs. Do not turn every unknown into a question for the user or assign someone else's decision to them. Present these as briefing items rather than interrupting the report to ask the user or solve the issue.

For **Blockers**, describe current conditions actually preventing or materially delaying progress, the affected work, and the known dependency/owner or next unblocking action. An external dependency, risk, or unresolved issue is not automatically a blocker. Qualify suspected blockers and unknown ownership instead of inventing certainty, deadlines, or responsibility. Exclude conditions resolved or superseded later in the window; a material resolution may belong under yesterday's work.

If a question or blocker is tightly tied to one bullet in another section, add **Input needed:** or **Blocked by:** there when that reads more clearly. Use the dedicated sections for standalone or cross-topic items. Give each item one primary home; do not repeat the same approval, uncertainty, or dependency under focus, input, and blockers. When user input is itself blocking work, describe both the request and blocking consequence together.

## Format for a daily meeting

Write speaking notes the user can scan five minutes before a daily meeting and read from while talking. Open with a compact date such as **Daily briefing: Thursday, 19 November**. Do not open with time ranges, chat counts, or a coverage narrative. Do not display “last 24 hours” in the briefing, including its headings and footer; the retrieval window still applies internally. Do not use em dashes anywhere in the output. Use colons, commas, parentheses, or separate bullets instead.

Always show these four headings, in this order and with no parenthetical additions:

1. **What I did yesterday**
2. **My focus today**
3. **Input needed from me**
4. **Blockers**

Keep all four sections even when empty or when input needs/blockers were placed inline elsewhere. Under an empty section, put a single visible `-`; in Markdown, write `\-` so it renders as text rather than an empty list item. This means no standalone item was identified in the reviewed evidence, not proof that none exists. If missing history prevents a meaningful assessment, use a brief “History unavailable” note instead of implying an empty result.

Within each section, group items under short topic/project labels. Make a topic bullet a short action or outcome headline, not a paragraph. Use one level of sub-bullets to separate results, status, dependencies, and necessary caveats. Aim for roughly 5–12 words per bullet line where practical; this is guidance, not a word-count constraint. One point per line. If a line needs multiple clauses or unrelated facts, split it. Prefer compact labels such as **Pending:**, **Not deployed**, **Planned**, **Likely**, **Input needed:**, and **Blocked by:**. Do not concatenate complete sentences with semicolons to disguise a paragraph as a bullet.

Keep status and uncertainty accurate while shortening. Preserve material distinctions such as drafted versus sent or service-level testing versus end-to-end validation in short sub-bullets. Use a concise caveat where it changes the meaning; avoid repeated methodological explanations. Put the most consequential topics first, and keep today's list shorter when the evidence supports that.

Example shape using fictional work:

```markdown
## What I did yesterday

**Project Atlas**

- **Production setup** [1]
  - Moved 3 tickets into the sprint
  - Service connection ready
  - Pending: pipeline authorization and authentication test

## My focus today

**Project Atlas**

- **Likely: finish production setup** [1]
  - Review pipeline changes
  - Run authentication check

## Input needed from me

\-

## Blockers

\-
```

Favor useful coverage without creating a long activity log. Aim for roughly **8–15 substantive items across the whole briefing** on a busy day, including input needs and blockers. Supporting sub-bullets explain those items; they are not a reason to add many more topics or turn every item into a miniature report. Use fewer items on a quiet day and modestly more when important work warrants it. Usually 1–3 short sub-bullets are enough for an item. Do not fill a quota or add an exhaustive appendix.

Keep traceability unobtrusive: reuse source markers at topic/item level and put a short chat-title/date source footer after the four sections. Use valid source-provided links when available. Retain chat IDs and exact turn timestamps in the working evidence notes, but do not print a long UUID/timestamp index unless requested. Mention material coverage gaps in a short end note; routine retrieval details need not be narrated. Do not invent content to fill a section.
