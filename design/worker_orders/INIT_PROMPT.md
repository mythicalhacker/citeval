# Session initialization — see LAUNCH_PROMPTS.md

The ready-to-paste, detailed launch prompts now live in **`LAUNCH_PROMPTS.md`** (single source of
truth, to avoid drift): the one-time git bootstrap, the four detailed Claude Code build prompts
(C1, C3, C5, C4), the Claude Science C6a prompt, and the research status.

Quick component → work-order map:

| Component | Work-order | worktree |
|---|---|---|
| C1 ingestion & extraction | `WO-C1_ingestion_extraction.md` | `../citeval-c1` |
| C3 claim scope (Opus) | `WO-C3_claim_scope.md` | `../citeval-c3` |
| C5 reporting (extend) | `WO-C5_reporting.md` | `../citeval-c5` |
| C4 adjudicator (mock-first) | `WO-C4_adjudication_mockfirst.md` | `../citeval-c4` |
| C6a corpus (Claude Science) | `WO-C6a_corpus_generator.md` | — |
