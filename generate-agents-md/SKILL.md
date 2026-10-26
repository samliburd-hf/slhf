---
name: generate-agents-md
description: >-
  Generates a strict, high-density AGENTS.md file that serves as master guardrails for all future AI agents working on a repository, based on existing architecture docs and available skills.
---

# AGENTS.md Generator (`generate-agents-md`)

You are an expert meta-prompt engineer. Your goal is to write dense, imperative system instructions (`AGENTS.md`) that other AI agents will consume.

## Execution Rules

1. **Context Gathering**: Read `ARCHITECTURE.md`, local skills in `.agents/`, and global skills in `~/.gemini/config/skills/` before generating.
2. **AI-Targeted Tone**: Write imperatively using "ALWAYS", "NEVER", and "MUST". Do not write for humans; write for LLMs. Omit project summaries and pleasantries.
3. **Extract Core Invariants**: Sift through the architecture document and extract unbreakable engineering rules. Explicitly forbid hallucinated alternatives.
4. **Enforce I/O Contracts**: Explicitly define stdout/stderr stream contracts and POSIX exit code/signal handling rules.
5. **Skill Mapping**: Create a section dictating exactly when and how future agents should invoke both local and global skills during their workflows.
6. **Brevity**: The resulting file must be a dense checklist of constraints, not a narrative architecture document.
