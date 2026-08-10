# Product Decisions – SignalDesk

This document records intentional product and technical decisions for Phase 1 and beyond.

## Why CSV-first

Customer feedback often arrives as exports from support tools, app stores, surveys, or spreadsheets. CSV upload keeps the MVP simple, portable, and easy to demo without building integrations.

## Why Streamlit

Streamlit enables rapid iteration for a portfolio project. A single Python codebase can deliver upload, exploration, charts, and review workflows without a separate frontend stack.

## Why source-linked evidence

Product insights are only useful if a PM can verify them. Every theme, quote, and recommendation must link back to `feedback_id`s so reviewers can audit claims and reject unsupported conclusions.

## Why human approval

Automated analysis will be wrong on sarcasm, mixed sentiment, multilingual text, and edge cases. Human review states (`pending`, `approved`, `rejected`, `needs_more_evidence`) keep the product honest and portfolio-ready.

## Why local fallback

The app must run without paid API keys. Deterministic local methods (rules, TF-IDF, clustering) ensure the demo always works and provide a baseline for evaluating optional LLM improvements.

## Why transparent prioritization

Priority scores are prototypes, not objective truth. Showing formula components and adjustable weights helps PMs understand trade-offs instead of trusting a black-box ranking.

## What was intentionally not built (Phase 1)

- AI/LLM analysis
- CSV upload UI
- PII masking
- Database persistence
- Export functionality
- Real customer data
- External API integrations
- Multi-user authentication

These are deferred to later phases to keep each increment testable and reviewable.

## Phase 2 decisions

### Why return all rows plus valid_rows

Silent deletion hides data problems from PMs. Returning every row with `row_status` and `validation_errors` makes exclusions auditable and prepares the Streamlit data-quality screen.

### Why ambiguous mappings fail explicitly

Guessing whether `comment` or `message` is the feedback body would corrupt evidence links. Explicit mappings protect traceability.

### Why duplicate text is a warning

Duplicate IDs break identity; duplicate text may be legitimate (many customers reporting the same outage). Warnings surface the pattern without dropping evidence.

### What was intentionally not built (Phase 2)

- PII masking
- AI analysis
- Streamlit upload UI
- SQLite persistence
- Export functionality

## Phase 3 decisions

### Why regex detection for the MVP

Regex is deterministic, offline, and easy to test without API keys. It provides a baseline privacy layer before optional LLM analysis.

### Why UPI detection has precedence over email

Both value types can contain `@`. Detecting UPI first prevents misclassifying synthetic handles like `user@upi` as email and protects evidence traceability.

### Why original and masked text are separate

PMs need local traceability to verify quotes, but external processing must never receive raw sensitive text. Dual columns enforce that boundary.

### Why ambiguous patterns require review

Context-free numeric patterns (Aadhaar-like groups, card sequences, standalone PAN-like tokens) can false-positive on order numbers or dates. Flagging them for human review keeps the product honest.

### Known limitations and future improvements

- No personal-name detection
- No ML-based NER
- Regex may miss obfuscated or non-standard formats
- Future phases may add configurable pattern packs and ML-assisted review queues

### Rating range alignment (Phase 3 fix)

`FeedbackRecord` now matches Phase 2 ingestion: optional ratings must be between **1 and 5**. Zero was removed to keep schema validation consistent with the data-quality layer.

## Phase 4 decisions

### Why local deterministic analysis before LLM integration

A working offline baseline is required for demos, tests, and comparison. Local rules ensure the app functions without API keys and provide an auditable fallback.

### Why masked_text is mandatory

Analysis must never process raw customer text that may contain PII. Phase 4 enforces `masked_text` and rejects direct analysis of `feedback_text`.

### Why keyword rules for known fintech themes

Indian fintech feedback has recurring, well-defined issue types (payments, refunds, KYC, OTP). Keyword and phrase rules are transparent, editable, and return matched terms for evidence traceability.

### Why multiple themes are supported

Real feedback often contains multiple independent problems (e.g. refund delay plus app performance). Forcing a single theme would discard evidence.

### Why TF-IDF is batch-only

TF-IDF requires a document corpus. Fitting on one text is meaningless. Batch-level fallback handles low-confidence keyword results without overriding strong matches.

### Why K-Means is exploratory only

Cluster IDs indicate textual similarity, not validated product themes. Keeping clustering separate from classification prevents unvalidated groups from altering severity or theme labels.

### Why sentiment must not determine severity

A neutral-toned security alert may still be critical. Severity rules inspect financial and security context independently.

### What is deferred to Phase 6

- Streamlit dashboard (upload → insights)
- Human review persistence and export
- SQLite storage

## Phase 5 decisions

### Why primary and secondary counts are separate

Feedback can express multiple independent problems. Tracking primary and secondary counts separately preserves how strongly each theme was classified without collapsing multi-theme records into a single label.

### Why a feedback record counts only once per theme mention_count

Double-counting the same record would inflate theme frequency and mislead prioritization. `mention_count` deduplicates by `feedback_id` while still allowing separate primary and secondary tallies.

### Why quotes must be exact masked excerpts

PMs must audit insights against source feedback. Exact excerpts from `masked_text` preserve traceability and privacy. Summarized or invented quotes break the evidence chain.

### Why unsupported quotes are rejected

A quote that does not appear in masked source text or does not support the theme cannot serve as evidence. Rejected quotes generate warnings rather than being displayed as proof.

### Why evidence strength is heuristic

Frequency and confidence alone do not prove root cause or business impact. The weak/moderate/strong labels are transparent prototype rules, not statistical guarantees.

### Why prioritization is transparent

PMs need to understand why one theme ranks above another. Showing `frequency_score`, `severity_score`, and `confidence_score` avoids a black-box ranking.

### Why K-Means does not affect product priority

Cluster IDs reflect textual similarity, not validated product themes. Using cluster size as a priority proxy would elevate unvalidated groups.

### What is deferred to Phase 6

- Streamlit dashboard UI
- Human review persistence and approval workflow
- Export to CSV, JSON, and Markdown
- SQLite persistence

## Phase 6 decisions

### Why Streamlit was selected

Streamlit enables a fast, Python-native dashboard for a portfolio MVP without building a separate frontend. It fits the CSV-upload → inspect → review workflow and keeps the focus on analysis transparency rather than UI polish.

### Why business logic remains outside app.py

Loading, cleaning, masking, analysis, aggregation, and prioritization live in dedicated `src/` modules with pytest coverage. `app.py` orchestrates the workflow; `src/ui_helpers.py` handles formatting, filtering, and session helpers. This keeps the dashboard testable and avoids duplicating data-loader logic in the UI layer.

### Why session state is used for the MVP

Persistent storage (SQLite, cloud) adds complexity and security review overhead for a prototype. Streamlit `session_state` is sufficient to demonstrate the full workflow while making clear that data does not survive a session reset.

### Why persistent storage is deferred

Uploaded customer feedback should not be written to disk without explicit retention policies. Phase 7 will add opt-in persistence with appropriate safeguards.

### Why masked text is shown by default

When PII is detected, the dashboard defaults to masked text to reduce accidental exposure in previews and record detail. Original text is shown only when no PII was detected and the user disables the masked-only toggle.

### Why priority score components are visible

PMs must understand why one theme ranks above another. The Theme detail section surfaces `frequency_score`, `severity_score`, and `confidence_score` alongside the prototype disclaimer.

### What is deferred to Phase 7

- SQLite persistence for review decisions
- Export to CSV, JSON, and Markdown
- Evaluation dashboard UI
- Optional LLM layer
- PDF export
