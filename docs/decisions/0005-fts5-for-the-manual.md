# 0005: SQLite FTS5 instead of embeddings for the Design Manual

**Status:** accepted (2026-11-17)

## Context

The assistant cites the company Design Manual when it explains a rule or an error. The
manual is small: seven short Markdown files, each in Spanish and English. The first
portfolio project (`local-rag-ollama`) already shows hybrid retrieval with embeddings
and a reranker. The online demo runs as one container without Ollama, so an embedding
model would mean either a second model provider or an embeddings API.

## Decision

Index `docs/manual/{es,en}/` into a **SQLite FTS5** table at startup, one row per
section (file, heading, language, text), ranked with `bm25`. The
`search_design_manual(query)` tool returns the top passages with a stable source id
(for example `02-revisions#skipped-letters`) that the model cites and the UI links.

## Consequences

- No model, vector store or network call for retrieval, so the cloud demo, CI and tests
  behave the same way.
- Keyword search can miss paraphrases. The manual is short and written for this tool, so
  that's mitigated by clear headings, a FAQ file, and keeping both languages. The model
  also receives the deterministic validator's error with its manual reference, so the
  most important citations don't depend on search at all.
- If evaluation (Phase 6) shows misses that matter, an embedding index can be added
  behind the same tool without changing the agent.
