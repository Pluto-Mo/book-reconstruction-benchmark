# Project instructions

This repository is an independent Harbor benchmark project for high-compression reconstruction of nonfiction books.

Before making material design decisions, read these foundational documents in full:

1. `docs/benchmark-v1.md`
2. `docs/instruction-variants.md`
3. `docs/cognitive-structure-contract.md`
4. `docs/discourse-reconstruction-contract.md`
5. `docs/rubric-production.md`
6. `docs/paperbench-adaptation.md`
7. `docs/harbor-mapping.md`

Project invariants:

- One book is one Harbor task; the full benchmark is one Harbor dataset.
- The repository root is a dataset workspace, not a task root. Runnable tasks live under `tasks/<book-id>/`; `templates/book-task/` is only a scaffold.
- Every instantiated task must preserve Harbor's canonical root files: `instruction.md`, `task.toml`, `environment/Dockerfile`, optional `solution/solve.sh`, and `tests/test.sh`. Extra rubric and verifier files belong under `tests/`.
- A task is not part of the dataset until it is added to `dataset.toml` with `harbor add`.
- Codex builds the benchmark. Harbor is the harness. The first pilot uses Claude Code as the evaluated agent scaffold.
- Later models enter through adapters. Never fork the task prompt, scaffold, tools, verifier, or budgets by model when claiming a model comparison.
- The primary public-use scenario is AI-assisted compressed co-reading for a time-constrained serious nonfiction reader, not a magazine commission, review, publication draft, or study-note handout.
- The default public instruction condition is `natural`: it states the reader's use case and meaningful quality preferences but does not provide book-specific task analysis or gold content.
- `explicit` and `minimal` are instruction-information ablations, not alternative leaderboard prompts. When used, they must be instantiated as isolated standard Harbor Tasks with the same source, length, scaffold, tools, budgets, verifier, gold cards, judge, and aggregation as `natural`.
- Instruction variants are defined by information sufficiency, not by superficial prompt length. `explicit` may reveal more high-level quality preferences but never book-specific gold relations, paths, cases, edges, probes, or weights. `minimal` intentionally under-specifies those preferences and is diagnostic only.
- Never mix `natural`, `explicit`, and `minimal` results into one primary leaderboard score. V1 primary results use `natural`; `explicit - natural` and `natural - minimal` may be reported as diagnostics.
- V1 has two distinct evaluation dimensions: `cognitive_structure` and `discourse_reconstruction`.
- Cognitive structure measures whether book-specific propositions, typed relations, paths, stance, boundaries, and constitutive material are preserved under compression.
- Discourse reconstruction measures (a) recovery of source-grounded authorial edges and (b) editorial coherence inside the reconstructed article.
- Public instructions must be clear about the real reader-facing task but must not reveal book-specific gold relations, authorial edges, sampling panels, probes, or weights.
- Every book has its own source-anchored cognitive graph: proposition/material nodes, typed directed relations, and required or alternative paths.
- The smallest cognitive scored leaf is a judgeable relation, not a keyword, topic, isolated proposition, or holistic impression.
- Relations may be independently judged, but they must remain attached to their parent structure and path; never pool them as an unstructured atom bag.
- Nodes must preserve argumentative role, stance owner, and epistemic status when those distinctions affect meaning.
- Constitutive cases are required cognitive structure; illustrative cases may be replaceable or optional.
- A terminal conclusion is not independently double-counted outside the path that produces it.
- Authorial edges come from a human-reviewed pool of meaningful source-anchor relations. Never sample arbitrary paragraph pairs from the Cartesian product of a book.
- Cognitive correctness gates an authorial-edge score. Do not reward the same semantic relation twice; the discourse score only measures rhetorical function, hierarchy, and downstream use after the content gate passes.
- Editorial coherence is measured from candidate-internal discourse relations and controlled perturbations, not by a holistic “flow” or “human-like writing” score.
- Frozen edge panels and probe-selection algorithms must be identical across compared models. Do not resample after seeing formal outputs.
- Pairwise judges must use A/B position reversal; conflicting outcomes become a tie or disagreement, not a forced win.
- Pure sentence-level style imitation, author identification, and generic “human feel” remain outside V1.
- Evidence location and semantic adjudication are separate runtime stages.
- Judges may reconstruct what the submission explicitly expresses, but must not supply missing substantive bridge claims from the source book.
- The evaluated agent environment is no-network by default. Any remote LLM judge must run in a Harbor-supported verifier network configuration, preferably a separate verifier environment with hidden tests baked into `tests/Dockerfile`.
- Declared artifacts must include every agent output needed by a separate verifier, including `/app/submission.md`.
- `/logs/verifier/reward.json` may contain only numeric values. Put status strings, versions, quotes, reasons, edge panels, perturbation outcomes, and judge traces in separate verifier log files.
- Agent-generated Book Cards and Discourse Cards remain drafts until a human owner approves them.
- Runtime scoring should be automatic. Human judgment is allowed upstream to approve gold cards, Oracle outputs, source-edge pools, and calibration anchors.
- LLM judges should decide frozen narrow criteria. They must not directly invent the total score.
- Pilot reporting keeps cognitive relation coverage, complete core path rate, authorial edge recovery, editorial coherence, and their submetrics separate until calibration justifies a scalar formula.
- Aggregation is deterministic and auditable.
- Each book is normalized before cross-book macro averaging; never pool all leaves, edges, or probes across books.
- Multiple rollouts use the mean as the main result. Best-of-k is a separate diagnostic.
- Fixed-length tasks form the main leaderboard. No-length runs are an ablation and must not be mixed into the main score.
- Do not commit copyrighted book text or secrets. Book sources under `environment/source/` are ignored by default.
- Frozen Book Cards and Discourse Cards are tied to source-document and linked-card SHA-256 values.
- Any schema, prompt, panel, weight, probe, or aggregation change after formal outputs exist requires a new version and a full rerun.

The template is deliberately not a runnable benchmark task yet: no book, finalized Book Card, finalized Discourse Card, Oracle response, production verifier, or dataset entry has been approved.
