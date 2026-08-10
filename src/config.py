"""Application configuration constants for SignalDesk."""

from pathlib import Path

# Application metadata
APP_NAME: str = "SignalDesk"
APP_TITLE: str = "SignalDesk – Voice-of-Customer Copilot"
ENVIRONMENT: str = "development"

# Paths
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
SAMPLE_FEEDBACK_PATH: Path = DATA_DIR / "sample_feedback.csv"
EVALUATION_SET_PATH: Path = DATA_DIR / "evaluation_set.csv"

# Upload limits
MAX_UPLOAD_SIZE_MB: int = 10
MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# CSV schema
REQUIRED_CSV_COLUMNS: tuple[str, ...] = ("feedback_id", "feedback_text")
OPTIONAL_CSV_COLUMNS: tuple[str, ...] = (
    "source",
    "date",
    "rating",
    "user_type",
    "region",
    "product_area",
    "language",
)

EVALUATION_CSV_COLUMNS: tuple[str, ...] = (
    "feedback_id",
    "feedback_text",
    "expected_theme",
    "expected_sentiment",
    "expected_severity",
    "expected_product_area",
)

# Supported labels (used by schemas and future analysis phases)
SUPPORTED_SENTIMENTS: tuple[str, ...] = (
    "positive",
    "neutral",
    "negative",
    "mixed",
    "unknown",
)

SUPPORTED_SEVERITIES: tuple[str, ...] = (
    "low",
    "medium",
    "high",
    "critical",
)

SUPPORTED_INTENTS: tuple[str, ...] = (
    "complaint",
    "praise",
    "question",
    "request",
    "bug_report",
    "unknown",
)

SUPPORTED_REVIEW_STATUSES: tuple[str, ...] = (
    "pending",
    "approved",
    "rejected",
    "needs_more_evidence",
)

# Fintech domain themes (reference list for future classification)
FINTECH_THEMES: tuple[str, ...] = (
    "payment_failure",
    "refund_delay",
    "kyc_problem",
    "login_authentication",
    "transaction_status",
    "customer_support",
    "fees",
    "app_performance",
    "usability",
    "security_concern",
    "feature_request",
)

# LLM configuration placeholder (not used in Phase 1)
LLM_ENABLED: bool = False

# CSV ingestion (Phase 2)
SUPPORTED_CSV_EXTENSIONS: tuple[str, ...] = (".csv",)
SUPPORTED_CSV_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8")

# Column aliases: internal field -> accepted source column names (normalized)
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "feedback_id": ("feedback_id", "id", "review_id", "ticket_id"),
    "feedback_text": ("feedback_text", "feedback", "review", "comment", "text", "message"),
    "source": ("source", "channel", "origin"),
    "date": ("date", "created_at", "timestamp"),
    "rating": ("rating", "score", "stars"),
    "user_type": ("user_type", "segment", "customer_segment"),
    "region": ("region", "location", "city", "state"),
    "product_area": ("product_area", "category", "feature_area"),
    "language": ("language", "lang"),
}

INTERNAL_COLUMNS: tuple[str, ...] = REQUIRED_CSV_COLUMNS + OPTIONAL_CSV_COLUMNS

# Rating validation range for ingestion (MVP)
MIN_RATING: float = 1.0
MAX_RATING: float = 5.0

# Row status labels used during cleaning
ROW_STATUS_VALID: str = "valid"
ROW_STATUS_WARNING: str = "warning"
ROW_STATUS_ERROR: str = "error"

# PII masking tokens (Phase 3)
PII_MASK_TOKENS: dict[str, str] = {
    "EMAIL": "[EMAIL_REDACTED]",
    "PHONE": "[PHONE_REDACTED]",
    "UPI": "[UPI_REDACTED]",
    "AADHAAR": "[AADHAAR_REDACTED]",
    "ACCOUNT": "[ACCOUNT_REDACTED]",
    "TRANSACTION_ID": "[TRANSACTION_ID_REDACTED]",
    "CARD": "[CARD_REDACTED]",
    "PAN": "[PAN_REDACTED]",
}

# Synthetic UPI handles supported for deterministic tests (not all real-world UPI handles)
SYNTHETIC_UPI_HANDLES: tuple[str, ...] = ("upi",)
