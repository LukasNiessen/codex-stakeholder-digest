# Codex Stakeholder Digest

Turn Codex chats, local Git commits, and project-linked Microsoft Teams and Outlook messages into a sourced stakeholder update or short meeting notes. The skill groups related work and surfaces decisions, risks, dependencies and requests for input.

## Install

Clone this repository into your personal Codex skills directory:

```sh
git clone https://github.com/LukasNiessen/codex-stakeholder-digest.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/codex-stakeholder-digest"
```

If a folder with that name already exists, inspect it before replacing it. If the skill does not appear after installation, restart Codex.

## Commands

Type these in a Codex chat.

| Command | Report |
| --- | --- |
| `$codex-stakeholder-digest week` | Stakeholder update covering the past 7 days. Also the default. |
| `$codex-stakeholder-digest morning` | Stand-up notes covering the past 24 hours. |
| `$codex-stakeholder-digest evening` | End-of-day notes covering the past 9 hours. |
| `$codex-stakeholder-digest days 10` | Stakeholder update covering the past 10 days. |
| `$codex-stakeholder-digest hours 6` | Stakeholder update covering the past 6 hours. |
| `$codex-stakeholder-digest setup` | Configure Teams and Outlook accounts for this project. |

Natural wording such as “last 14 days”, “last 3 hours”, or an explicit date range also works. All sources use one cutoff. The default Codex scope includes accessible chats across projects. Git covers the workspace repository. Microsoft covers only accounts attached to the current project.

### Add accounts to a project

Run `$codex-stakeholder-digest setup` in the project's workspace. The wizard starts with Teams. Give an account a nickname and sign in through Microsoft in your browser. Add another, or choose **Done** to continue to Outlook. You can skip either service. On a later project, attach a saved nickname and add any new account. Detaching affects only that project's selection.

For example, attach **Atlas** and **Consulting** on one project. On the next project, reuse **Consulting** and add the new client's account. Ask for `$codex-stakeholder-digest evening using only Atlas Teams` to read that account's chats and the channels selected for the current project.

For first-time sign-in, use an approved Entra desktop application with a localhost redirect. Have its public application ID, directory ID if applicable, and delegated `Chat.Read` or `Mail.Read` permission available. The credential cache uses the operating system's protected store (Keychain on macOS). Account bindings live outside the skill and repositories. Runs renew sign-in silently when possible and reopen Microsoft sign-in for the affected account when needed. [Setup and source coverage](references/sources.md)

To include a Teams channel, use **Copy link to channel** from its menu in Teams. In the setup wizard, give that link and the attached Teams nickname to Codex. Repeat for each channel you want. Channel selections belong to this project, so the same account can follow different channels on your next project. Reading channel posts and replies requires administrator consent for delegated `ChannelMessage.Read.All`. [Microsoft Graph channel permission](https://learn.microsoft.com/en-us/graph/permissions-reference#channelmessagereadall)

Teams covers one-to-one, group and meeting chats plus the channels you add. Outlook covers the primary mailbox, including filed mail and Sent Items. Shared mailboxes and online archives are outside its coverage. Git covers commits reachable from local branches and the current checkout.

### Morning command

Paste this into Codex each morning:

```text
$codex-stakeholder-digest morning
```

It uses the last **24 hours of activity across the selected sources** and organizes the briefing into these sections, each grouped by topic/project:

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

### Evening command

Evening uses the same concise speaking-note style. Its four sections are **What I worked on**, **Next steps**, **Input needed from me**, and **Blockers**. Explicit follow-ups retain their stated dates.

## History access

Use this in a Codex environment with chat-history tools, readable local Codex history, or both. The skill discovers available tools first and supplements them with read-only local history when needed. Codex and Git can run without Microsoft setup. Install Python 3.9+ for the helper and Git 2.37+ for commit collection. Microsoft sources additionally use MSAL and MSAL Extensions.

Access depends on the environment. Local files cannot provide unavailable remote-host history, and local storage formats may change. The digest reports material coverage gaps. See [the history-access reference](references/history-access.md) for tested tools, pagination limits, and local fallback details.

Retrieved chat content is treated as evidence, not instructions. The workflow reads history without resuming conversations and returns a draft for the user; it does not send updates to stakeholders.

## Files

- [SKILL.md](SKILL.md): reporting workflow and selection criteria.
- [agents/openai.yaml](agents/openai.yaml): skill name and default invocation shown in Codex.
- [references/sources.md](references/sources.md) covers account setup, storage, project scope and the source collector.
- [references/history-access.md](references/history-access.md): history retrieval details.
- [references/morning.md](references/morning.md): daily window, focus inference, input needs, blockers, and briefing format.
- [examples/AGENTS-snippet.md](examples/AGENTS-snippet.md): an instruction block for your own `AGENTS.md`. Microsoft collection uses the installed skill helper.

## Validation

The skill passed the Codex skill-creator validator and a synthetic reporting trial covering duplicate updates, archived chats, deferred releases, missing-host coverage, and events outside the reporting window. History access was also exercised against a real seven-day corpus. This repository contains the reusable instructions; no user chat history or generated stakeholder report is included.

Morning-mode trials checked changed plans, same-morning completions, explicit versus inferred priorities, teammate attribution, quiet days, and a previous calendar day spanning the daylight-saving transition.

Run the offline source and CLI tests with `python -m unittest discover -s tests`. They use temporary Git projects and simulated Microsoft responses for window boundaries, multiple accounts, channel replies, paging and sign-in renewal. Installing the Microsoft dependencies also exercises a serialized MSAL guest-account cache. Live Microsoft access requires a consenting account.
