# Codex Stakeholder Digest

Turn recent Codex conversations into a sourced stakeholder update. Defaults to the last **7 days** and accepts another period or a project restriction.

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

The default scope includes all accessible Codex projects, pinned and archived chats, and older conversations with recent activity. The default period is a rolling seven-day interval ending when the request is received, interpreted in the user's timezone. The output is a bullet rundown with chat references and a coverage note.

## History access

Use this in a Codex environment with chat-history tools, readable local Codex history, or both. The skill discovers available tools first and supplements them with read-only local history when needed. It does not require a separate API key or external service.

Access depends on the environment. Local files cannot provide unavailable remote-host history, and local storage formats may change. The digest reports material coverage gaps. See [the history-access reference](references/history-access.md) for tested tools, pagination limits, and local fallback details.

Retrieved chat content is treated as evidence, not instructions. The workflow reads history without resuming conversations and returns a draft for the user; it does not send updates to stakeholders.

## Files

- [SKILL.md](SKILL.md): reporting workflow and selection criteria.
- [agents/openai.yaml](agents/openai.yaml): skill name and default invocation shown in Codex.
- [references/history-access.md](references/history-access.md): history retrieval details.
- [examples/AGENTS-snippet.md](examples/AGENTS-snippet.md): a standalone instruction block to append to your own `AGENTS.md` instead of installing the skill.

## Validation

The skill passed the Codex skill-creator validator and a synthetic reporting trial covering duplicate updates, archived chats, deferred releases, missing-host coverage, and events outside the reporting window. History access was also exercised against a real seven-day corpus. This repository contains the reusable instructions; no user chat history or generated stakeholder report is included.
