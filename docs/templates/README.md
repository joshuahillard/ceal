# Prompt System Templates

Plug-and-play templates for setting up a structured AI-driven development workflow on any project.

## Files

| Template | What it creates | Fill-in time |
|----------|----------------|--------------|
| PROJECT_LEDGER_TEMPLATE.md | Timeline, decision log, sprint retros | 30 min for initial backfill |
| RUNTIME_PROMPTS_TEMPLATE.md | Core Contract, Task Cards, Mode Packs | 15 min to customize rules |
| CLAUDE_CODE_MASTER_PROMPT_TEMPLATE.md | Claude Code custom instructions | 10 min |
| PERSONA_LIBRARY_TEMPLATE.md | Engineering thinking frameworks | 5 min (binding section only) |
| PROMPT_ARCHITECTURE_TEMPLATE.md | Human-facing design rationale | 5 min |

## Setup for a new project

1. Copy all 5 templates to your new project's docs/ folder
2. Rename: replace "TEMPLATE" with your project name
3. Fill in the Core Contract first (stack, rules, key paths) — this is the foundation
4. Fill in the Project Binding section of the Persona Library
5. Start the Project Ledger with Phase 0
6. Paste the Claude Code Master Prompt into your tool's custom instructions
7. Start working using Task Cards from the Runtime Prompts

## What goes where

- **Pasted into AI sessions:** Core Contract, Task Cards, Mode Packs, Snapshots (from RUNTIME_PROMPTS)
- **Pasted into tool config:** Claude Code Master Prompt (one time setup)
- **Never pasted into AI:** Architecture doc, Persona Library, Project Ledger, this README
