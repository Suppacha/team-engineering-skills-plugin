# Data classification and access

Owner: Suppacha. Baseline 2.0.0. Ask the project/data owner when classification is unknown; default to Confidential until clarified.

| Class | Examples | AI handling baseline |
| --- | --- | --- |
| Public | Published source, public documentation | Approved account; check license and task scope. |
| Internal | Nonpublic planning, internal code without secrets | Use only an organization-approved provider/account and need-to-know context. |
| Confidential | Proprietary designs, customer identifiers, contracts | Explicit data-owner and organization approval for the exact provider/use; minimize and redact. |
| Restricted | Credentials, private keys, production dumps, regulated sensitive records | Do not place in prompts, tool output, public issues or this repository; use synthetic fixtures and approved non-AI procedures. |

- Classification applies to output, logs, screenshots and test fixtures as well as input.
- Public repository visibility does not make every local file public. Never enumerate private directories or read .env files just because they exist.
- Access only task-relevant files and approved environments. Authorization for review does not imply authorization to edit, deploy or message third parties.
- Do not store customer/company policy details in this public framework repository. Keep project-specific restrictions in the appropriate controlled repository.
- The bootstrap reads the selected release, not project source or secrets; its snapshot contains policy, registry and hashes only. No access-control enforcement is created.
