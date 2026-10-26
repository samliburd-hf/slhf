# SLHF Agent Skills

Custom agentic skills for Google Antigravity, Claude Code, and AI pair-programming workflows.

## Available Skills

| Skill | Description |
| :--- | :--- |
| **`docs-architect`** | Formulates publication-grade, 11-section architectural manuals (`ARCHITECTURE.md`) with Mermaid diagrams and AST validation. |
| **`generate-agents-md`** | Generates dense, imperative `AGENTS.md` system prompt guardrail files. |
| **`gtm-tag-downloader`** | Downloads Google Tag Manager (GTM) tag configurations as JSON setups via `gtm-mcp-server`, optionally bundling associated triggers and referenced variables. |

---

## Installation via `npx skills`

Install all skills into any project workspace:

```bash
npx skills add samliburd-hf/slhf --all -y
```

Or install individual skills:

```bash
# GTM Tag Downloader
npx skills add samliburd-hf/slhf --skill gtm-tag-downloader -y

# Documentation Architect
npx skills add samliburd-hf/slhf --skill docs-architect -y

# Agent Guardrails Generator
npx skills add samliburd-hf/slhf --skill generate-agents-md -y
```

---

## License

Proprietary & Confidential — Hookflash.
