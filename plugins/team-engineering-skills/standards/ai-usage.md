# AI usage standard

Owner: Suppacha. Baseline 2.0.0.

- Each member uses their own approved Codex or Claude Code account and subscription; do not share passwords, API keys, cookies or sessions.
- The developer chooses the client. Skill routing occurs within that client and does not automatically select, start or bill another provider.
- Local execution means tools run on the developer's machine. Cloud model requests can transmit code, prompts and tool output off the machine. Check the approved provider, account data controls, retention rules and data classification before use.
- Do not send confidential/restricted material unless the organization and data owner explicitly approve the provider and exact use. Redact or substitute synthetic data when in doubt.
- Use the minimum relevant context and skill set. State which skill was selected and why; distinguish tool execution from advice or a plan.
- A human remains responsible for code review, correctness, licensing and release decisions. Never claim tests, reviews, permissions or deployments happened without evidence.
- No organization-wide prompt monitoring, background upload or provider-switching service is included. Feedback is voluntarily submitted, sanitized and manual.
- Instructions in AGENTS.md, CLAUDE.md and SKILL.md guide behavior but cannot guarantee compliance. Higher-priority client policy and explicit user authorization still apply.
