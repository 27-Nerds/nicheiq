# NicheIQ Documentation Index

Complete documentation for the NicheIQ autonomous market research system.

## Documentation Structure

### 📘 User Documentation (Root Directory)

**Start here if you're new to NicheIQ:**

- **[README.md](../README.md)** - Project overview, features, and quick start
- **[GETTING_STARTED.md](../GETTING_STARTED.md)** - Step-by-step setup and first research run
- **[ENV_REFERENCE.md](../ENV_REFERENCE.md)** - Complete environment variable reference

### 🤖 AI Context (Root Directory)

**For Claude Code and AI-assisted development:**

- **[CLAUDE.md](../CLAUDE.md)** - Essential project knowledge, current patterns, and best practices
- **[PROMPT_OPTIMIZATION_BEST_PRACTICES.md](../PROMPT_OPTIMIZATION_BEST_PRACTICES.md)** - Prompt engineering guidelines

### 🏗️ Technical Documentation (docs/)

**Deep dives for developers and contributors:**

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, design philosophy, and data flows
- **[PATTERNS.md](PATTERNS.md)** - Reusable code patterns and recipes for common tasks
- **[FEATURES.md](FEATURES.md)** - Advanced features (checkpoints, token monitoring, multi-model)
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Known issues, bug fixes, and debugging strategies

### 📦 Archive (docs/archive/)

**Historical implementation reports from development:**

- **[archive/README.md](archive/README.md)** - Index of archived reports

## When to Use Each Document

### I want to...

**...get started with NicheIQ**
→ [README.md](../README.md) → [GETTING_STARTED.md](../GETTING_STARTED.md)

**...understand the architecture**
→ [ARCHITECTURE.md](ARCHITECTURE.md)

**...add a new crew or feature**
→ [PATTERNS.md](PATTERNS.md) → [ARCHITECTURE.md](ARCHITECTURE.md)

**...fix a bug or debug an issue**
→ [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**...configure checkpoints or token monitoring**
→ [FEATURES.md](FEATURES.md)

**...work with Claude Code on this project**
→ [CLAUDE.md](../CLAUDE.md)

**...understand environment variables**
→ [ENV_REFERENCE.md](../ENV_REFERENCE.md)

**...find historical implementation details**
→ [archive/README.md](archive/README.md)

## Documentation Principles

### User-Facing vs AI-Facing

**User-Facing** (README, GETTING_STARTED, ENV_REFERENCE):
- Setup instructions
- Usage examples
- Configuration options
- Troubleshooting basics

**AI-Facing** (CLAUDE.md):
- Current architectural patterns
- Best practices for development
- Essential project knowledge
- Quick reference commands

**Developer-Facing** (docs/ directory):
- Deep technical details
- Design decisions and trade-offs
- Code patterns and templates
- Historical context

### Keeping Documentation Current

**When to update each file:**

- **CLAUDE.md**: Add new patterns, update core architecture (keep < 400 lines)
- **ARCHITECTURE.md**: Document design decisions, add new pipeline stages
- **PATTERNS.md**: Add code templates when patterns become reusable
- **FEATURES.md**: Document new configuration options or advanced features
- **TROUBLESHOOTING.md**: Archive bug fixes after resolution
- **README.md**: Major feature additions, update quick start
- **GETTING_STARTED.md**: Setup process changes
- **ENV_REFERENCE.md**: New environment variables

## Contributing to Documentation

### Adding New Content

1. **New pattern/best practice** → Add to CLAUDE.md if essential, otherwise PATTERNS.md
2. **Bug fix/workaround** → Document in TROUBLESHOOTING.md
3. **Architectural change** → Update ARCHITECTURE.md
4. **New feature** → Document in FEATURES.md, update README.md
5. **Configuration option** → Add to ENV_REFERENCE.md

### Documentation Quality Standards

✅ **Do**:
- Keep CLAUDE.md focused and concise
- Separate "how it works" (ARCHITECTURE) from "how to build" (PATTERNS)
- Document the "why" not just the "what"
- Include code examples in PATTERNS.md
- Cross-reference related docs

❌ **Don't**:
- Put historical bug fixes in CLAUDE.md (use TROUBLESHOOTING.md)
- Duplicate content across multiple files
- Let any single file grow beyond ~300-400 lines
- Include setup instructions in ARCHITECTURE.md
- Mix user guides with technical architecture

## Quick Links

### Most Frequently Referenced

1. [CLAUDE.md](../CLAUDE.md) - Daily AI development context
2. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - When things break
3. [PATTERNS.md](PATTERNS.md) - Copy-paste code templates
4. [ENV_REFERENCE.md](../ENV_REFERENCE.md) - Configuration lookup

### For Specific Tasks

- **Add a new crew**: [PATTERNS.md#adding-new-crews](PATTERNS.md#adding-new-crews)
- **Checkpoint system**: [FEATURES.md#checkpoint--resume-system](FEATURES.md#checkpoint--resume-system)
- **Token monitoring**: [FEATURES.md#token-monitoring--cost-control](FEATURES.md#token-monitoring--cost-control)
- **Knowledge sources**: [PATTERNS.md#modifying-knowledge-sources](PATTERNS.md#modifying-knowledge-sources)
- **Guardrails**: [PATTERNS.md#implementing-guardrails](PATTERNS.md#implementing-guardrails)
- **Async issues**: [TROUBLESHOOTING.md#async-event-loop-issues](TROUBLESHOOTING.md#async-event-loop-issues)
- **Pydantic bug**: [TROUBLESHOOTING.md#pydantic-schema-parser-bug](TROUBLESHOOTING.md#pydantic-schema-parser-bug)

## Documentation Statistics

| File | Purpose | Target Audience | Size |
|------|---------|----------------|------|
| README.md | Overview | All users | ~200 lines |
| GETTING_STARTED.md | Setup guide | New users | ~300 lines |
| CLAUDE.md | AI context | Claude Code | ~350 lines |
| ENV_REFERENCE.md | Config reference | Operators | ~200 lines |
| ARCHITECTURE.md | Technical details | Developers | ~250 lines |
| PATTERNS.md | Code recipes | Developers | ~150 lines |
| FEATURES.md | Advanced features | Power users | ~200 lines |
| TROUBLESHOOTING.md | Bug fixes | All developers | ~300 lines |

---

**Last Updated**: 2025-01-22
**Documentation Version**: 2.0 (Restructured)
