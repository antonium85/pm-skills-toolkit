# pm-skills-toolkit

A growing toolbox of Claude skills built for day-to-day Product Manager work — audits, prototyping, inbox triage, prompt crafting, and whatever comes next.

Each skill lives in Claude settings for actual use, and gets a copy checked in here so it's versioned, backed up, and easy to browse or roll back. Expect this list to keep growing as new ideas turn into skills.

## Skills

| Skill | Description |
|---|---|
| [`accessibility-audit`](skills/accessibility-audit/SKILL.md) | Audits a11y (WCAG/RGAA) of a web page, HTML/React component, or mockup, with a severity-ranked report. |
| [`copypage`](skills/copypage/SKILL.md) | Recreates a web page as a self-contained HTML prototype from screenshots, source code, or live browser access. |
| [`email-digest`](skills/email-digest/SKILL.md) | Summarizes and triages the last 7 days of Gmail into a prioritized digest. |
| [`prompt-builder`](skills/prompt-builder/SKILL.md) | Interactively builds a structured prompt (role, task, format, constraints) with the user. |
| [`market-intelligence`](skills/market-intelligence/SKILL.md) | Daily news brief on a subject: Google News RSS via a deterministic script, top 10 candidates, Tavily cross-check, 3 summarized articles, with a seen/rejected ledger. Can email the brief as an HTML newsletter through Resend ("email me"). |

## Adding a new skill

1. Create the skill in Claude settings first, and use/test it until it's stable.
2. Copy its `SKILL.md` into a new `skills/<skill-name>/` folder here (include any supporting assets/scripts if the skill has them).
3. Add a row to the table above.
4. Commit.
