# SignalDesk – Voice-of-Customer Copilot

A CSV-first, evidence-focused product that helps product managers analyze customer feedback and convert it into source-linked product insights.

**The current repository contains Phase 1 foundation, Phase 2 data ingestion, and Phase 3 PII detection/masking. AI analysis has not yet been implemented.**

---

## Target User

Product managers, founders, product operations managers, and customer-support managers who receive customer feedback from multiple sources and need to identify recurring problems and decide what to investigate.

## Initial Use Case

Synthetic Indian fintech customer feedback covering payments, refunds, KYC, authentication, fees, support, performance, usability, and security topics.

## Phase 3 Status

Phase 3 adds deterministic regex-based PII detection and masking:

- Detect email, phone, UPI, Aadhaar-like numbers, account numbers, transaction IDs, card-like numbers, and PAN-like identifiers
- Preserve `original_text` and produce `masked_text` for safe downstream use
- DataFrame helper adds PII metadata columns
- No external API calls; all processing is local and in-memory

**Not yet implemented:** Sentiment/theme analysis, Streamlit upload UI, human review, exports, or LLM integration.

## Synthetic Data Notice

**All feedback in this repository is synthetic.** It was created for demonstration and testing only. It does not represent real customers, real transactions, or real business outcomes. Do not treat sample outputs as evidence of product performance.

## Current Scope (Phase 3)

| Included | Not included |
|----------|--------------|
| Phase 1 foundation and schemas | Streamlit upload UI |
| Phase 2 CSV ingestion and validation | Sentiment/theme analysis |
| PII detection and masking (`src/pii_detector.py`) | Clustering and insights |
| `original_text` + `masked_text` columns | Human review workflow |
| DataFrame PII helper | Export reports |
| Phase 1–3 pytest suites | LLM integration |

## Future Scope

- CSV upload with column mapping
- Data quality validation and duplicate detection
- PII detection and masking (original + masked text)
- Local rule-based analysis with TF-IDF and clustering
- Optional LLM provider with deterministic fallback
- Evidence-linked theme insights and transparent prioritization
- Human review states (pending, approved, rejected, needs_more_evidence)
- Evaluation dashboard with accuracy metrics
- Export to CSV, JSON, and Markdown

## Project Structure

```
signaldesk-voc-copilot/
├── app.py                  # Streamlit placeholder
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
│   └── pii_detector.py
├── tests/
│   ├── __init__.py
│   ├── test_phase1.py
│   ├── test_data_loader.py
│   ├── test_cleaner.py
│   └── test_pii_detector.py
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

## Known Limitations (Phase 3)

- PII detection is regex-based and may miss or over-detect sensitive values
- No Streamlit UI integration yet
- No sentiment, theme, clustering, or LLM analysis
- No persistence, human review, or export
- Sample datasets remain synthetic and PII-free

## Privacy Note

Treat all uploaded customer feedback as potentially sensitive. Phase 1 includes only synthetic data. Future phases will mask PII before any external processing and never commit real customer data to the repository.

## Roadmap

| Phase | Focus |
|-------|-------|
| **1** | Foundation, schemas, synthetic data, tests |
| **2** | CSV loading, validation, data quality report |
| **3** (current) | PII detection and masking |
| **4** | Local analysis engine (sentiment, theme, severity) |
| **5** | Theme aggregation, evidence, prioritization |
| **6** | Streamlit dashboard (upload → insights) |
| **7** | Human review and export |
| **8** | Evaluation module |
| **9** | Optional LLM layer |
| **10** | Portfolio polish and documentation |

## License

MIT License — see [LICENSE](LICENSE).
