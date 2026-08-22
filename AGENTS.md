# Project instructions

This repository is an independent Harbor benchmark project for high-compression reconstruction of nonfiction books.

Before making material design decisions, read these foundational documents in full:

1. `docs/benchmark-v1.md`
2. `docs/cognitive-structure-contract.md`
3. `docs/rubric-production.md`
4. `docs/paperbench-adaptation.md`
5. `docs/harbor-mapping.md`

Project invariants:

- One book is one Harbor task; the full benchmark is one Harbor dataset.
- Codex builds the benchmark. Harbor is the harness. The first pilot uses Claude Code as the evaluated agent scaffold.
- Later models enter through adapters. Never fork the task prompt, scaffold, tools, verifier, or budgets by model when claiming a model comparison.
- The V1 construct is preservation of book-specific cognitive structure under compression, not generic summarization quality.
- Public instructions must be clear about the construct but must not reveal book-specific gold relations, paths, cases, or weights.
- Every book has its own source-anchored cognitive graph: proposition/material nodes, typed directed relations, and required or alternative paths.
- The smallest scored leaf is a judgeable relation, not a keyword, topic, isolated proposition, or holistic impression.
- Relations may be independently judged, but they must remain attached to their parent structure and path; never pool them as an unstructured atom bag.
- Nodes must preserve argumentative role, stance owner, and epistemic status when those distinctions affect meaning.
- Cognitively functional organization belongs in the main structure score. Pure sentence-level style imitation is outside V1.
- Constitutive cases are required structure; illustrative cases may be replaceable or optional.
- A terminal conclusion is not independently double-counted outside the path that produces it.
- Evidence location and semantic adjudication are separate runtime stages.
- Judges may reconstruct what the submission explicitly expresses, but must not supply missing substantive bridge claims from the source book.
- Agent-generated Book Cards remain drafts until a human owner approves them.
- Runtime scoring should be automatic. Human judgment is allowed upstream to approve gold cards, Oracle outputs, and calibration anchors.
- LLM judges should decide frozen narrow criteria. They must not directly invent the total score.
- Pilot reporting keeps cognitive relation coverage and complete core path rate separate until calibration justifies a scalar formula.
- Aggregation is deterministic and auditable.
- Each book is normalized before cross-book macro averaging; never pool all leaves across books.
- Multiple rollouts use the mean as the main result. Best-of-k is a separate diagnostic.
- Fixed-length tasks form the main leaderboard. No-length runs are an ablation and must not be mixed into the main score.
- Do not commit copyrighted book text or secrets. Book sources under `environment/source/` are ignored by default.
- A frozen Book Card is tied to the SHA-256 of its source Markdown.
- Any schema, prompt, weight, or aggregation change after formal outputs exist requires a new version and a full rerun.

The template task is deliberately not runnable yet: no book, gold card, Oracle response, or production verifier has been approved.
