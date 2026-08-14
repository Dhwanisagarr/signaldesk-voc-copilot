# SignalDesk – Voice-of-Customer Copilot

A CSV-first, evidence-focused product that helps product managers analyze customer feedback and convert it into source-linked product insights.

**The current repository contains Phase 8B: Consolidated 3-Step B2B Product Workflow, Inline Evidence Drawer, Configurable Domain Taxonomies, and Embedded Review Decisions. LLM integration and evaluation module are deferred.**

---

## Target User

Product managers, founders, product operations managers, and customer-support managers who receive customer feedback from multiple sources and need to identify recurring problems and decide what to investigate.

## Consolidated 3-Step Workflow

SignalDesk reorganizes Voice-of-Customer analysis into a streamlined 3-step B2B product workflow:

1. **Import Data (`pages/01_Import.py`)** — Upload CSV exports, select domain taxonomy presets (`Fintech`, `SaaS`, `E-Commerce`, `General`), run column auto-mapping, and audit dataset privacy health.
2. **Insight Workspace (`pages/02_Workspace.py`)** — Master-detail issue hub featuring human-readable Priority Urgency badges (`P0 Critical`, `P1 High`, `P2 Medium`, `P3 Low`), embedded review decision controls (`Approve for Roadmap`, `Needs Evidence`, `Dismiss`), and an **Inline Evidence Drawer** for deep quote exploration without context switching.
3. **Export & Share (`pages/03_Export.py`)** — Rendered executive report preview, Markdown export, evidence CSV downloads, and structured JSON export.

Technical floating-point scores (`priority_score`, `frequency_score`, `severity_score`, `confidence_score`) are tucked cleanly into expandable **Methodology & Score Details** sections.

## Phase 7 Status

Phase 7 adds local SQLite review persistence and privacy-safe masked exports:

- **SQLite Review Persistence** — Human review statuses (`pending`, `approved`, `rejected`, `needs_more_evidence`) and reviewer notes are stored locally in `outputs/reviews.db` across app restarts. Only metadata is stored—no customer feedback, original text, or raw PII is ever written to disk.
- **Privacy-Enforced Exports** — Pre-export validation verifies that `original_text`, raw `feedback_text`, or unmasked PII patterns are not present before generating exports.
- **Export Formats:**
  1. Masked Analysed Records CSV (`analyzed_records_masked.csv`)
  2. Masked Theme Insights CSV (`theme_insights_masked.csv`)
  3. Masked Theme Insights JSON (`theme_insights_masked.json`)
  4. Executive Markdown Report (`voc_executive_report_masked.md`)

## Database Location & Management

- **File location:** `outputs/reviews.db` (gitignored).
- **Single-user prototype:** Local storage for a single-user workflow.
- **Clearing decisions:** Use the **Review database administration** expander in the Review section (requires explicit checkbox confirmation), or delete the file `outputs/reviews.db` directly.

## Export Policy & Privacy

Exports contain **masked text only**. Every export run executes pre-export privacy checks (`validate_export_privacy`). If forbidden fields (`original_text`, `feedback_text`) or unmasked PII patterns are detected, the export is rejected with a clear error.

*Disclaimer included in all exports:*
> "Results describe patterns in the uploaded dataset only. Suggested actions are prototype outputs and require product-manager validation."

## Current Scope (Phase 7)

| Included | Not included |
|----------|--------------|
| Phases 1–6 (foundation through dashboard) | Cloud database persistence |
| SQLite review persistence (`outputs/reviews.db`) | PDF / Excel exports |
| Masked exports (CSV, JSON, Markdown) | LLM / external API integration |
| Pre-export PII and original-text validation | Multi-user authentication & collaboration |
| Streamlit dashboard with 10 sections | Evaluation dashboard UI |
| Comprehensive pytest suites (259 passing tests) | Automatic data collection |

## Project Structure

```
signaldesk-voc-copilot/
├── app.py                  # Streamlit dashboard (Phase 6–7)
├── requirements.txt
├── pytest.ini
├── .env.example
├── README.md
├── PRODUCT_DECISIONS.md
├── LICENSE
├── data/
│   ├── sample_feedback.csv
│   └── evaluation_set.csv
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── schemas.py
│   ├── data_loader.py
│   ├── cleaner.py
│   ├── pii_detector.py
│   ├── analysis_config.py
│   ├── sentiment.py
│   ├── theme_classifier.py
│   ├── clustering.py
│   ├── analysis_pipeline.py
│   ├── evidence.py
│   ├── prioritization.py
│   ├── review_store.py     # SQLite persistence for human review
│   ├── export.py           # Masked CSV, JSON, Markdown exports & privacy validation
│   └── ui_helpers.py       # Dashboard formatting, review sync, and session helpers
├── tests/
│   ├── test_phase1.py
│   ├── test_data_loader.py
│   ├── test_cleaner.py
│   ├── test_pii_detector.py
│   ├── test_sentiment.py
│   ├── test_theme_classifier.py
│   ├── test_clustering.py
│   ├── test_analysis_pipeline.py
│   ├── test_evidence.py
│   ├── test_prioritization.py
│   ├── test_review_store.py # SQLite store unit tests
│   ├── test_export.py       # Masked export unit tests
│   └── test_ui_helpers.py
└── outputs/                # Generated exports & reviews.db (gitignored)
```
├── .env.example
├── README.md
├── PRODUCT_DECISIONS.md
├── LICENSE
├── data/
│   ├── sample_feedback.csv
│   └── evaluation_set.csv
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── schemas.py
│   ├── data_loader.py
│   ├── cleaner.py
│   ├── pii_detector.py
│   ├── analysis_config.py
│   ├── sentiment.py
│   ├── theme_classifier.py
│   ├── clustering.py
│   ├── analysis_pipeline.py
│   ├── evidence.py
│   ├── prioritization.py
│   └── ui_helpers.py       # Dashboard formatting & session helpers
├── tests/
│   ├── test_phase1.py
│   ├── test_data_loader.py
│   ├── test_cleaner.py
│   ├── test_pii_detector.py
│   ├── test_sentiment.py
│   ├── test_theme_classifier.py
│   ├── test_clustering.py
│   ├── test_analysis_pipeline.py
│   ├── test_evidence.py
│   ├── test_prioritization.py
│   └── test_ui_helpers.py
└── outputs/                # Generated exports (gitignored)
```

## Python Version

**Python 3.11** (tested with 3.11.5)

## Setup

```bash
# Clone and enter the project
cd signaldesk-voc-copilot

# Activate the existing virtual environment
source .venv/bin/activate

# Install Phase 1 dependencies
pip install -r requirements.txt

# Optional: copy environment template
cp .env.example .env
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Run the App

```bash
python -m streamlit run app.py
```

## Data Schema

### Sample feedback (`data/sample_feedback.csv`)

| Column | Required | Description |
|--------|----------|-------------|
| `feedback_id` | Yes | Unique identifier |
| `feedback_text` | Yes | Customer feedback text |
| `source` | No | Channel (e.g. in_app, email, phone) |
| `date` | No | Feedback date (YYYY-MM-DD) |
| `rating` | No | Numeric rating (**1–5** for ingestion validation) |
| `user_type` | No | e.g. retail, SME, new_user |
| `region` | No | Indian city/region |
| `product_area` | No | Product area label |
| `language` | No | e.g. English, Hinglish |

### Evaluation set (`data/evaluation_set.csv`)

| Column | Required | Description |
|--------|----------|-------------|
| `feedback_id` | Yes | Unique identifier |
| `feedback_text` | Yes | Feedback text |
| `expected_theme` | Yes | Manually assigned theme |
| `expected_sentiment` | Yes | positive, neutral, negative, mixed, unknown |
| `expected_severity` | Yes | low, medium, high, critical |
| `expected_product_area` | Yes | Product area label |

## Phase 2 – Data Ingestion & Quality

### Supported input formats

- `.csv` files only (max **10 MB** by default, configurable via `MAX_UPLOAD_SIZE_MB`)
- UTF-8 and UTF-8 with BOM encodings
- Input sources: filesystem path, raw bytes, `BytesIO`, or file-like objects

### Required and optional columns

**Required:** `feedback_id`, `feedback_text`

**Optional:** `source`, `date`, `rating`, `user_type`, `region`, `product_area`, `language`

### Column aliases

| Internal field | Accepted aliases |
|----------------|------------------|
| `feedback_id` | `id`, `review_id`, `ticket_id` |
| `feedback_text` | `feedback`, `review`, `comment`, `text`, `message` |
| `source` | `channel`, `origin` |
| `date` | `created_at`, `timestamp` |
| `rating` | `score`, `stars` |
| `user_type` | `segment`, `customer_segment` |
| `region` | `location`, `city`, `state` |
| `product_area` | `category`, `feature_area` |
| `language` | `lang` |

If multiple columns match the same internal field, ingestion raises an `AmbiguousMappingError`. Provide an explicit mapping via `column_mapping`.

### Rating range

Ratings are optional. When provided, they must be numeric values between **1 and 5** inclusive. Invalid ratings mark the row as **invalid**.

### Date handling

Dates are optional. Original values are preserved in `date`. Parseable dates also populate `date_normalized` (ISO `YYYY-MM-DD`). Unparseable dates produce a **warning**; the row may still be valid.

### Duplicate handling

- **Duplicate `feedback_id`:** all affected rows are marked **error** and excluded from `valid_rows`.
- **Duplicate `feedback_text`:** affected rows receive a **warning** but remain in `valid_rows` unless another error exists.

### Invalid-row handling (no silent deletion)

Phase 2 returns:

1. **`all_rows`** – every uploaded row with `_row_number`, `row_status`, and `validation_errors`
2. **`valid_rows`** – rows where `row_status != "error"`
3. **`report`** – a `DataQualityReport` with counts and `row_issues`

Invalid rows are never silently removed. Each excluded row appears in `all_rows` and in `report.row_issues` with a reason.

### Programmatic usage

```python
from src.data_loader import load_and_validate_feedback

result = load_and_validate_feedback("data/sample_feedback.csv")
print(result.report.total_rows, result.report.valid_rows, result.report.invalid_rows)
valid_df = result.valid_rows
```

### Phase 2 limitations

- No Streamlit upload UI yet
- No AI analysis
- No persistence beyond in-memory DataFrames
- Unsupported encodings (e.g. Latin-1) are rejected rather than guessed

## Phase 3 – PII Detection & Masking

### Supported PII categories

| Category | Masking token |
|----------|---------------|
| Email | `[EMAIL_REDACTED]` |
| Indian phone | `[PHONE_REDACTED]` |
| UPI ID | `[UPI_REDACTED]` |
| Aadhaar-like number | `[AADHAAR_REDACTED]` |
| Bank account number | `[ACCOUNT_REDACTED]` |
| Transaction ID | `[TRANSACTION_ID_REDACTED]` |
| Card-like number | `[CARD_REDACTED]` |
| PAN-like identifier | `[PAN_REDACTED]` |

### UPI versus email

UPI values are detected **before** email addresses. Values such as `user@upi` (synthetic test handle) are classified as UPI, not email. Standard email addresses like `user@example.com` remain email detections. UPI detection requires context (e.g. “UPI ID”, “VPA”) or an allowed synthetic handle such as `@upi`.

### Missing-value handling

`None`, empty strings, whitespace-only strings, `pandas.NA`, and `NaN` are handled safely. Missing input returns empty masked text, `detected=False`, and warning `"Input text is missing."` — no regex is applied.

### Original versus masked text

- **`original_text`** — preserved locally for traceability (in-memory only)
- **`masked_text`** — safe version for future analysis or external model calls

**Phase 3 makes no external API calls.** Masked text is the only text that should be sent to external providers in future phases.

### DataFrame helper

```python
from src.pii_detector import mask_dataframe_feedback

masked_df = mask_dataframe_feedback(valid_rows, text_column="feedback_text")
```

Adds columns: `original_text`, `masked_text`, `pii_detected`, `pii_entity_types`, `pii_review_required`. The input DataFrame is not modified in place.

### Rating consistency

`FeedbackRecord` and Phase 2 ingestion both enforce optional ratings in the **1–5** range.

### False-positive limitations

Regex masking is **not complete anonymization**. Context-free numeric patterns (standalone 12-digit groups, card-like sequences, PAN-like tokens) may produce false positives and are flagged with `pii_review_required=True` when ambiguous or when multiple PII categories appear.

Personal names are **not** detected in Phase 3.

### Programmatic usage

```python
from src.pii_detector import detect_and_mask_pii

result = detect_and_mask_pii("Contact user@example.com for help.")
safe_text = result.masked_text  # use for future analysis
```

## Phase 4 – Local Analysis Engine

### Local-only analysis

All analysis is deterministic and runs locally. No LLM or external API calls are made. The engine uses **`masked_text` only** — never `original_text` or raw `feedback_text`.

### Sentiment labels

`positive`, `negative`, `neutral`, `mixed`, `unknown` — determined by keyword matching with explainable matched terms. Sentiment is independent from severity.

### Themes (primary + secondary)

Supported themes include: `payment_failure`, `refund_delay`, `kyc_problem`, `login_authentication`, `otp_problem`, `transaction_status`, `fees`, `customer_support`, `app_performance`, `usability`, `security_concern`, `feature_request`, `other`, `unknown`.

Each record receives one **primary theme** and zero or more **secondary themes** when multiple independent problems are detected. Generic words like "problem" alone do not trigger classification.

### TF-IDF batch fallback

TF-IDF is fitted once per batch on masked texts. It is used only when keyword confidence is below threshold. It never overrides high-confidence keyword matches. Single-text classification does not fit TF-IDF.

### Exploratory clustering

K-Means assigns `cluster_id` metadata labeled as **exploratory similarity groups**. Clustering does **not** modify sentiment, themes, severity, intent, or confidence.

### Severity and intent

Severity (`low`, `medium`, `high`, `critical`, `unknown`) and intent (`complaint`, `praise`, `question`, `request`, `bug_report`, `unknown`) are rule-based and independent from sentiment. A positive review can still contain a critical security problem.

### Centralized configuration

Editable rules live in `src/analysis_config.py`: sentiment lexicon, theme keywords/phrases, severity phrases, intent terms, confidence thresholds, TF-IDF and clustering settings.

### Pipeline usage

```python
from src.data_loader import load_and_validate_feedback
from src.pii_detector import mask_dataframe_feedback
from src.analysis_pipeline import analyze_feedback_dataframe

loaded = load_and_validate_feedback("data/sample_feedback.csv")
masked = mask_dataframe_feedback(loaded.valid_rows)
output = analyze_feedback_dataframe(masked)  # requires masked_text column
```

### Unknown and human-review states

Rows with missing masked text, weak theme evidence, low confidence, or PII review flags receive `requires_human_review=True` and may have `primary_theme=unknown`.

### Phase 4 limitations

- Rule-based sentiment is not production-grade NLP
- TF-IDF fallback is exploratory, not semantic understanding
- K-Means clusters are not product themes
- No Streamlit UI integration

## Phase 5 – Theme Aggregation, Evidence & Prioritization

### Theme-level aggregation

Phase 5 aggregates Phase 4 `AnalysisResult` records into `ThemeInsight` objects. Each theme receives:

- **`primary_count`** — records where the theme is the primary theme
- **`secondary_count`** — records where the theme appears only as a secondary theme
- **`mention_count`** — unique feedback records mentioning the theme (primary or secondary, counted once)
- **`feedback_percentage`** — `mention_count / total_valid_feedback_records × 100`

All counts, percentages, averages, and distributions are computed in Python — not by an LLM.

### Primary vs secondary vs mention count

Because feedback can contain multiple themes, primary and secondary counts are tracked separately. A single record counts at most once toward `mention_count` for a theme, even if the same theme appeared in both roles (which should not happen in practice).

### Evidence-linked masked quotes

Representative quotes (max **3** per theme) must be exact matches or contiguous excerpts from `masked_text`. Quotes are never taken from `original_text`, never invented, and never grammar-corrected. Invalid quotes are rejected and excluded from display.

### Quote validation

`validate_quote()` checks:

- Feedback ID exists in the masked DataFrame
- Quote matches `masked_text` exactly or as a substring
- Quote supports the associated theme classification

Validation statuses: `valid`, `invalid`, `missing_source`, `missing_feedback_id`, `requires_review`.

### Evidence strength (prototype heuristic)

| Label | Criteria (simplified) |
|-------|----------------------|
| **weak** | Fewer than 3 supporting records, invalid/missing quotes, or low confidence |
| **moderate** | At least 3 records with valid masked quotes and reasonable confidence |
| **strong** | At least 5 records, high confidence, valid quotes, multiple sources when available |

Evidence strength is a prototype heuristic — not statistical truth. High frequency alone does not make evidence strong.

### Prototype prioritization score

```
priority_score = frequency_score × severity_score × confidence_score
```

Where:

- `frequency_score = mention_count / total_valid_feedback_records`
- `severity_score = average_known_severity / 5` (unknown severity excluded)
- `confidence_score = average confidence of supporting records`

Every score includes the warning: **"Prototype prioritization score – requires PM judgment."** The score does not automatically create roadmap items.

K-Means cluster IDs do **not** affect priority.

### Suggested actions are not confirmed decisions

`possible_root_causes` and `suggested_product_actions` use deterministic templates from theme rules. They are labeled as interpretations requiring PM validation — not confirmed product decisions or business impact claims.

### Pipeline usage

```python
from src.data_loader import load_and_validate_feedback
from src.pii_detector import mask_dataframe_feedback
from src.analysis_pipeline import analyze_feedback_dataframe
from src.evidence import aggregate_theme_insights
from src.prioritization import prioritize_theme_insights

loaded = load_and_validate_feedback("data/sample_feedback.csv")
masked = mask_dataframe_feedback(loaded.valid_rows)
analysis = analyze_feedback_dataframe(masked)
aggregation = aggregate_theme_insights(analysis.results, masked)
insights = prioritize_theme_insights(
    aggregation.insights,
    aggregation.total_valid_feedback_records,
)
```

### Phase 5 limitations

- Root causes and suggested actions are template-based, not LLM-generated
- Evidence strength and priority scores are prototype heuristics
- Secondary theme detection depends on Phase 4 classification quality

## Phase 6 – Streamlit Dashboard

### Dashboard sections

| Section | Purpose |
|---------|---------|
| Home | Overview, disclaimers, sample CSV downloads |
| Upload & mapping | CSV upload, inferred/manual column mapping |
| Data quality | Full quality report, continue with valid rows |
| Privacy & masking | PII summary, masked preview, run analysis |
| Feedback explorer | Filterable per-record analysis table |
| Theme insights | Priority-sorted theme cards with warnings |
| Theme detail | Distributions, quotes, priority components |
| Review | In-session status and reviewer notes |
| Limitations & methodology | Design transparency |

### Manual testing checklist

1. Start the app: `streamlit run app.py`
2. Download sample CSV from Home
3. Upload `data/sample_feedback.csv`
4. Confirm inferred column mapping
5. Continue with valid rows on Data quality
6. Verify PII summary shows counts without raw PII
7. Run local analysis
8. Confirm theme insights and masked evidence quotes appear
9. Change a review status and add a note
10. Clear session data and confirm state resets
11. Upload invalid file type — verify readable error

### Phase 6 limitations

- No persistent storage or export
- Review decisions lost when session clears or browser closes
- Re-upload required after session clear
- No LLM or external API integration

## Known Limitations (Phase 6)

- Analysis quality depends on keyword coverage and masked text quality
- Hinglish support is limited to configured terms
- No LLM enhancement or evaluation dashboard yet
- No persistence, export, or cross-session human review workflow
- Evidence strength and prioritization require PM judgment
- Dashboard stores uploaded data in browser session memory only

## Privacy Note

Treat all uploaded customer feedback as potentially sensitive. Phase 1 includes only synthetic data. Future phases will mask PII before any external processing and never commit real customer data to the repository.

## Roadmap

| Phase | Focus |
|-------|-------|
| **1** | Foundation, schemas, synthetic data, tests |
| **2** | CSV loading, validation, data quality report |
| **3** | PII detection and masking |
| **4** | Local analysis engine (sentiment, theme, severity) |
| **5** | Theme aggregation, evidence, prioritization |
| **6** (current) | Streamlit dashboard (upload → insights) |
| **7** | Human review persistence and export |
| **8** | Evaluation module |
| **9** | Optional LLM layer |
| **10** | Portfolio polish and documentation |

## License

MIT License — see [LICENSE](LICENSE).
