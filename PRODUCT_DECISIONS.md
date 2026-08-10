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
