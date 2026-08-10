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
