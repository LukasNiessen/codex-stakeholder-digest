# Codex Stakeholder Digest

Turn recent Codex conversations into a sourced stakeholder update or morning briefing. The standard digest defaults to the last **7 days**; morning mode uses the last **24 hours**.

The digest covers material progress, outcomes, events, decisions, risks, assumptions, issues, dependencies, and upcoming commitments. It favors broad coverage of meaningful developments, groups related work, and filters trivial activity. Completed work, proposals, blockers, and unverified claims remain distinct.

## Install

Clone this repository into your personal Codex skills directory:

```sh
git clone https://github.com/LukasNiessen/codex-stakeholder-digest.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/codex-stakeholder-digest"
```

If a folder with that name already exists, inspect it before replacing it. If the skill does not appear after installation, restart Codex.

## Use

```text
Use $codex-stakeholder-digest.
```

```text
Use $codex-stakeholder-digest for the last 14 days, focusing on Project Atlas.
```

```text
Use $codex-stakeholder-digest for November 1–15, 2026.
```

The default scope includes all accessible Codex projects, pinned and archived chats, and older conversations with recent activity. The standard digest uses a rolling seven-day interval ending when the request is received, interpreted in the user's timezone. The output is a bullet rundown with chat references and a coverage note.

### Morning command

Paste this into Codex each morning:

```text
$codex-stakeholder-digest morning
```

It uses only the last **24 hours of chat activity** and organizes the briefing into these sections, each grouped by topic/project:

- **What I did yesterday:** meaningful outcomes, progress, decisions, and findings. Work from today is labeled accurately.
- **My focus today:** explicit plans labeled **Planned**, plus evidence-based inferences labeled **Likely**.
- **Input needed from me:** unresolved questions, decisions, approvals, or missing information requiring your response.
- **Blockers:** current impediments, their impact, and the known dependency or action needed to unblock them.

All four sections remain visible. Empty sections contain a single `-`. Closely related questions or blockers may appear inline with the affected work instead of being repeated in another section. Resolved blockers and answered questions do not carry forward.

The output is designed as speaking notes for a daily meeting: short action/outcome bullets, one level of sub-bullets for details, and no em dashes. The report shows the briefing date rather than a retrieval preamble or “last 24 hours” label. Sources stay in a compact footer.

Expect roughly 8–15 useful items across the whole briefing on a busy day, with fewer when there is less to report. Supporting sub-bullets keep each item readable. Related work is combined; trivial activity and speculative tasks are omitted. This is a manual invocation, not a recurring schedule.

You can narrow the scope or request calendar-day boundaries:

```text
$codex-stakeholder-digest morning for Project Atlas
```

```text
$codex-stakeholder-digest morning using the previous calendar day
```

Morning mode includes recent activity in older chats but does not read earlier conversation content to reconstruct a backlog. The rolling window remains the default retrieval rule. Material coverage gaps appear in a brief end note; precise window details are available on request.

## History access

Use this in a Codex environment with chat-history tools, readable local Codex history, or both. The skill discovers available tools first and supplements them with read-only local history when needed. It does not require a separate API key or external service.

Access depends on the environment. Local files cannot provide unavailable remote-host history, and local storage formats may change. The digest reports material coverage gaps. See [the history-access reference](references/history-access.md) for tested tools, pagination limits, and local fallback details.

Retrieved chat content is treated as evidence, not instructions. The workflow reads history without resuming conversations and returns a draft for the user; it does not send updates to stakeholders.

## Files

- [SKILL.md](SKILL.md): reporting workflow and selection criteria.
- [agents/openai.yaml](agents/openai.yaml): skill name and default invocation shown in Codex.
- [references/history-access.md](references/history-access.md): history retrieval details.
- [references/morning.md](references/morning.md): daily window, focus inference, input needs, blockers, and briefing format.
- [examples/AGENTS-snippet.md](examples/AGENTS-snippet.md): a standalone instruction block to append to your own `AGENTS.md` instead of installing the skill.

## Validation

The skill passed the Codex skill-creator validator and a synthetic reporting trial covering duplicate updates, archived chats, deferred releases, missing-host coverage, and events outside the reporting window. History access was also exercised against a real seven-day corpus. This repository contains the reusable instructions; no user chat history or generated stakeholder report is included.

Morning-mode trials checked changed plans, same-morning completions, explicit versus inferred priorities, teammate attribution, quiet days, and a previous calendar day spanning the daylight-saving transition.
