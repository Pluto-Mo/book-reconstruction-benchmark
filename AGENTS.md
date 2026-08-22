# Project instructions

This repository is an independent Harbor benchmark project for high-compression reconstruction of nonfiction books.

Before making material design decisions, read these foundational documents in full:

1. `docs/benchmark-v1.md`
2. `docs/paperbench-adaptation.md`
3. `docs/rubric-production.md`
4. `docs/harbor-mapping.md`

Project invariants:

- One book is one Harbor task; the full benchmark is one Harbor dataset.
- Codex builds the benchmark. Harbor is the harness. The first pilot uses Claude Code as the evaluated agent.
- Later models enter through API adapters. Never fork the task prompt or verifier by model; comparison requires one frozen submission contract.
- The V1 construct is preservation of book-specific cognitive structure under compression, not generic summarization quality.
- The top-level Meta-Rubric is shared, but every book has its own source-anchored relation and atom tree.
- Agent-generated Book Cards remain drafts until a human owner approves them.
- Runtime scoring should be automatic. Human judgment is allowed upstream to approve gold cards and calibration anchors.
- LLM judges should retrieve evidence and decide narrow binary criteria. They must not directly invent the total score.
- Aggregation is deterministic and auditable.
- Each book is normalized before cross-book macro averaging; never pool all leaves across books.
- Multiple rollouts use the mean as the main result. Best-of-k is a separate diagnostic.
- Fixed-length tasks form the main leaderboard. No-length runs are an ablation and must not be mixed into the main score.
- Do not commit copyrighted book text or secrets. Book sources under `environment/source/` are ignored by default.
- A frozen Book Card is tied to the SHA-256 of its source Markdown.
- Current V1 weights are provisional. Any change must be recorded in the design document with its reason and expected consequence.

The template task is deliberately not runnable yet: no book, gold card, oracle response, or production verifier has been approved.
