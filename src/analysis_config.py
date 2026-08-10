"""Analysis rule configuration for SignalDesk local engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

# ---------------------------------------------------------------------------
# Sentiment lexicon (deterministic, editable)
# ---------------------------------------------------------------------------

SENTIMENT_POSITIVE_TERMS: tuple[str, ...] = (
    "easy",
    "smooth",
    "fast",
    "helpful",
    "excellent",
    "convenient",
    "reliable",
    "good",
    "great",
    "love",
    "thank",
    "resolved",
    "achha",
    "अच्छा",
    "आसान",
)

SENTIMENT_NEGATIVE_TERMS: tuple[str, ...] = (
    "failed",
    "failure",
    "delay",
    "delayed",
    "blocked",
    "confusing",
    "terrible",
    "slow",
    "deducted",
    "unable",
    "pending",
    "reject",
    "rejected",
    "crash",
    "crashes",
    "freeze",
    "frustrating",
    "worst",
    "bad",
    "not received",
    "disconnected",
    "der",
    "खराब",
    "देर",
)

# Generic terms excluded from standalone theme matching
THEME_STOPWORDS: frozenset[str] = frozenset({"problem", "issue", "issues", "problems"})

# ---------------------------------------------------------------------------
# Theme rule configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThemeRuleConfig:
    """Keyword and phrase rules for a single analysis theme."""

    theme: str
    keywords: tuple[str, ...]
    phrases: tuple[str, ...]
    product_area: str
    default_severity: str
    default_intent: str
    subthemes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    suggested_action_template: str = ""


THEME_RULES: tuple[ThemeRuleConfig, ...] = (
    ThemeRuleConfig(
        theme="payment_failure",
        keywords=("payment failed", "transaction failed", "upi failed", "payment timeout", "deducted"),
        phrases=(
            "money deducted after failed payment",
            "money was deducted",
            "payment not received",
            "merchant did not receive",
        ),
        product_area="payments",
        default_severity="high",
        default_intent="complaint",
        subthemes={
            "deduction_after_failure": ("deducted", "money deducted", "amount deducted"),
            "gateway_failure": ("timeout", "gateway", "failed payment"),
        },
        suggested_action_template="Investigate payment gateway failures and deduction reconciliation.",
    ),
    ThemeRuleConfig(
        theme="refund_delay",
        keywords=("refund pending", "refund delayed", "waiting for refund", "refund not received"),
        phrases=(
            "refund still pending",
            "refund is still pending",
            "refund not credited",
            "waiting for refund",
        ),
        product_area="refunds",
        default_severity="high",
        default_intent="complaint",
        subthemes={
            "status_confusion": ("refund status", "processing", "stuck on processing"),
        },
        suggested_action_template="Review refund SLA breaches and status communication.",
    ),
    ThemeRuleConfig(
        theme="kyc_problem",
        keywords=("kyc failed", "kyc rejected", "kyc pending", "document upload", "verification problem"),
        phrases=("identity verification", "kyc verification rejected", "document upload failed"),
        product_area="kyc",
        default_severity="high",
        default_intent="complaint",
        subthemes={
            "document_upload": ("document upload", "upload failed", "upload keeps failing"),
            "verification_rejected": ("verification rejected", "kyc rejected"),
        },
        suggested_action_template="Review KYC rejection reasons and document upload reliability.",
    ),
    ThemeRuleConfig(
        theme="login_authentication",
        keywords=("cannot login", "can't login", "unable to login", "login failed", "account blocked"),
        phrases=("unable to access account", "locked out", "login blocked"),
        product_area="authentication",
        default_severity="high",
        default_intent="complaint",
        subthemes={
            "account_blocked": ("account blocked", "locked out"),
        },
        suggested_action_template="Investigate authentication failures and account lockout flows.",
    ),
    ThemeRuleConfig(
        theme="otp_problem",
        keywords=("otp delayed", "otp not received", "verification code", "otp not arriving"),
        phrases=("otp not received", "otp delayed", "verification code problem"),
        product_area="authentication",
        default_severity="medium",
        default_intent="complaint",
        subthemes={
            "delivery_delay": ("otp delayed", "otp not arriving", "not arriving"),
        },
        suggested_action_template="Review OTP delivery latency and retry guidance.",
    ),
    ThemeRuleConfig(
        theme="transaction_status",
        keywords=("transaction pending", "transaction history", "duplicate debit", "pending transaction"),
        phrases=("transaction status unclear", "missing transaction", "duplicate charge"),
        product_area="transactions",
        default_severity="medium",
        default_intent="complaint",
        subthemes={
            "pending_status": ("transaction pending", "pending since", "status unclear"),
            "missing_entry": ("missing transaction", "history missing"),
        },
        suggested_action_template="Audit transaction status updates and ledger visibility.",
    ),
    ThemeRuleConfig(
        theme="fees",
        keywords=("extra charge", "hidden fee", "service fee", "unexpected charge", "maintenance fee"),
        phrases=("convenience fee", "annual fee", "hidden charges"),
        product_area="pricing",
        default_severity="medium",
        default_intent="complaint",
        subthemes={
            "unexpected_fee": ("without prior notification", "unexpected charge", "hidden fee"),
        },
        suggested_action_template="Clarify fee disclosure and billing notifications.",
    ),
    ThemeRuleConfig(
        theme="customer_support",
        keywords=("customer support", "support team", "chat support", "call disconnected", "on hold"),
        phrases=("support has not replied", "kept me on hold", "generic replies"),
        product_area="customer_support",
        default_severity="medium",
        default_intent="complaint",
        subthemes={
            "long_wait": ("on hold", "long wait", "disconnected the call"),
            "unhelpful_response": ("generic replies", "could not explain"),
        },
        suggested_action_template="Review support responsiveness and escalation paths.",
    ),
    ThemeRuleConfig(
        theme="app_performance",
        keywords=("app crashes", "app crash", "slow load", "laggy", "battery drain", "app freezes"),
        phrases=("slow to load", "freezes on splash", "app is slow", "app is fast"),
        product_area="performance",
        default_severity="medium",
        default_intent="bug_report",
        subthemes={
            "crash": ("app crashes", "app crash", "crashes whenever"),
            "slow_performance": ("slow", "laggy", "load times"),
        },
        suggested_action_template="Profile performance regressions on affected devices.",
    ),
    ThemeRuleConfig(
        theme="usability",
        keywords=("confusing", "hard to understand", "too many steps", "unclear labels", "navigation"),
        phrases=("hard to understand", "too many taps", "labels are unclear"),
        product_area="usability",
        default_severity="low",
        default_intent="complaint",
        subthemes={
            "navigation": ("navigation menu", "labels are unclear"),
            "workflow_friction": ("too many steps", "too many taps"),
        },
        suggested_action_template="Simplify affected workflows and labeling.",
    ),
    ThemeRuleConfig(
        theme="security_concern",
        keywords=("fraud", "unauthorized transaction", "suspicious activity", "account hacked", "unknown device"),
        phrases=("did not authorize", "security settings", "session stays active"),
        product_area="security",
        default_severity="critical",
        default_intent="complaint",
        subthemes={
            "unauthorized_access": ("unauthorized", "unknown device", "did not attempt login"),
            "session_security": ("session stays active", "session remains active"),
        },
        suggested_action_template="Escalate suspected fraud and session-security issues.",
    ),
    ThemeRuleConfig(
        theme="feature_request",
        keywords=("please add", "would like", "feature request", "add option", "dark mode", "export to csv"),
        phrases=("please add", "would like", "add export"),
        product_area="other",
        default_severity="low",
        default_intent="request",
        subthemes={
            "new_feature": ("please add", "would like", "add option"),
        },
        suggested_action_template="Capture feature demand for product planning.",
    ),
)

ANALYSIS_THEMES: tuple[str, ...] = tuple(rule.theme for rule in THEME_RULES) + ("other", "unknown")

THEME_RULES_BY_NAME: dict[str, ThemeRuleConfig] = {rule.theme: rule for rule in THEME_RULES}

# ---------------------------------------------------------------------------
# Severity rules (independent from sentiment)
# ---------------------------------------------------------------------------

SEVERITY_SCORES: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 4,
    "critical": 5,
    "unknown": 1,
}

SEVERITY_CRITICAL_PHRASES: tuple[str, ...] = (
    "unauthorized transaction",
    "suspected fraud",
    "account hacked",
    "money deducted after failed payment",
    "did not authorize",
    "fraud",
)

SEVERITY_HIGH_PHRASES: tuple[str, ...] = (
    "payment failed",
    "refund pending",
    "refund delayed",
    "kyc rejected",
    "cannot login",
    "unable to login",
    "account blocked",
    "transaction pending",
)

SEVERITY_MEDIUM_PHRASES: tuple[str, ...] = (
    "app crashes",
    "slow to load",
    "on hold",
    "confusing",
    "service fee",
    "otp delayed",
)

SEVERITY_LOW_PHRASES: tuple[str, ...] = (
    "would like",
    "please add",
    "dark mode",
    "wording",
    "labels are unclear",
)

# ---------------------------------------------------------------------------
# Intent rules
# ---------------------------------------------------------------------------

INTENT_PRAISE_TERMS: tuple[str, ...] = ("thank", "helpful", "resolved", "love the", "excellent", "good app")
INTENT_QUESTION_TERMS: tuple[str, ...] = ("how do i", "why was", "what is", "when will", "?")
INTENT_REQUEST_TERMS: tuple[str, ...] = ("please add", "would like", "please provide", "add option")
INTENT_BUG_TERMS: tuple[str, ...] = ("crash", "crashes", "freeze", "freezes", "bug", "not working")

# ---------------------------------------------------------------------------
# Product areas
# ---------------------------------------------------------------------------

PRODUCT_AREAS: tuple[str, ...] = (
    "payments",
    "refunds",
    "kyc",
    "authentication",
    "transactions",
    "pricing",
    "customer_support",
    "performance",
    "usability",
    "security",
    "other",
    "unknown",
)

# ---------------------------------------------------------------------------
# Confidence and review thresholds
# ---------------------------------------------------------------------------

THEME_PHRASE_WEIGHT: float = 2.0
THEME_KEYWORD_WEIGHT: float = 1.0
THEME_PRIMARY_MIN_CONFIDENCE: float = 0.35
THEME_SECONDARY_MIN_CONFIDENCE: float = 0.25
TFIDF_FALLBACK_MIN_SIMILARITY: float = 0.12
TFIDF_FALLBACK_MAX_CONFIDENCE: float = 0.55
SENTIMENT_MIXED_MIN_TERMS: int = 1
LOW_CONFIDENCE_REVIEW_THRESHOLD: float = 0.4

# ---------------------------------------------------------------------------
# TF-IDF and clustering settings
# ---------------------------------------------------------------------------

TFIDF_MAX_FEATURES: int = 5000
TFIDF_NGRAM_RANGE: tuple[int, int] = (1, 2)
CLUSTER_RANDOM_STATE: int = 42
CLUSTER_N_INIT: int = 10
CLUSTER_DEFAULT_K: int = 5
CLUSTER_MAX_K: int = 8
CLUSTER_REPRESENTATIVE_TERMS: int = 5
