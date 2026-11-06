# Codex repository instructions

## Scope
This repository contains an investment-recording application and a draft Japanese stock-analysis skill.
Do not place brokerage orders, interact with order-entry systems, or claim that a trade was executed.

## Project mission and roadmap (read before planning any task)

Read `docs/PROJECT_ROADMAP.md` before proposing or implementing work. It defines the
long-term objective, current phase, dependencies, acceptance criteria, and safety
boundaries. Read `docs/DEV_LOG_TEMPLATE.md` for evidence-based progress records.

At the start of each task, briefly state:
- North Star: verified, repeatable trading decisions and eventual safely audited automation.
- Current phase and why this task matters to that phase.
- Exact acceptance criteria, evidence to collect, and what remains prohibited.

At the end, report what was verified versus assumed, tests actually run, commit SHA,
remaining risks, and next actionable step. Never confuse offline mocks with live
API validation. Keep the daily trading journal separate from the development log.

## Stock analysis routing
When the user's request includes the Japanese keyword `解析鑑定`, consult
`.agents/skills/stock-analysis-triad/SKILL.md` before answering or modifying code.

- Follow the nine-section output contract in that file without skipping sections.
- Apply the three roles (ラファエル / リュミエル / クラリタ) and label unverified information.
- Never invent prices, technical indicator values, news, or portfolio holdings.
- If evidence is insufficient, complete the nine sections with explicit limitations.
- Do not use future information for historical-as-of analysis.
- Keep analysis separate from order execution.

## Verification
For manual acceptance cases, consult
`.agents/skills/stock-analysis-triad/TEST_PLAN.md`.
Run static checks with:
`python -m unittest discover -s tests -p 'test_stock_analysis_skill.py' -v`

## Skill discovery caveat
This AGENTS.md provides repository-level routing instructions.
It does not by itself prove that Codex has registered the SKILL.md as a native, automatically discoverable skill.
Confirm native skill discovery in a fresh Codex task on the feature branch and report that separately.

## Safety and change management
- Work on feature branches; do not modify main without explicit approval.
- Do not alter the canonical Obsidian analysis template or ratified covenant.
- Do not add brokerage credentials, secrets, or live-order integrations.
- Do not claim test success without a recorded run.
