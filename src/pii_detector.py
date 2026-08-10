"""Regex-based PII detection and masking for customer feedback text."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from src.config import PII_MASK_TOKENS, SYNTHETIC_UPI_HANDLES
from src.schemas import PIIEntity, PIIDetectionResult

MISSING_TEXT_WARNING = "Input text is missing."


@dataclass(frozen=True)
class _PatternSpec:
    """Compiled PII pattern with masking metadata."""

    entity_type: str
    pattern: re.Pattern[str]
    mask_token: str
    priority: int
    ambiguous: bool = False


# ---------------------------------------------------------------------------
# Pattern definitions (compiled once, documented for maintainability)
# ---------------------------------------------------------------------------

_UPI_HANDLES = "|".join(re.escape(handle) for handle in SYNTHETIC_UPI_HANDLES)

PII_PATTERN_SPECS: tuple[_PatternSpec, ...] = (
    _PatternSpec(
        entity_type="UPI",
        pattern=re.compile(
            rf"(?:(?:UPI\s*ID|VPA|payment\s+address|upi\s+id)\s*[:\-]?\s*)?"
            rf"([a-zA-Z0-9._-]+@(?:{_UPI_HANDLES}))\b",
            re.IGNORECASE,
        ),
        mask_token=PII_MASK_TOKENS["UPI"],
        priority=10,
    ),
    _PatternSpec(
        entity_type="EMAIL",
        pattern=re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        ),
        mask_token=PII_MASK_TOKENS["EMAIL"],
        priority=20,
    ),
    _PatternSpec(
        entity_type="PHONE",
        pattern=re.compile(
            r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{9}(?!\d)",
        ),
        mask_token=PII_MASK_TOKENS["PHONE"],
        priority=30,
    ),
    _PatternSpec(
        entity_type="AADHAAR",
        pattern=re.compile(
            r"(?:aadhaar|aadhar|uid|identity\s+number)\s*[:\-#]?\s*(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b",
            re.IGNORECASE,
        ),
        mask_token=PII_MASK_TOKENS["AADHAAR"],
        priority=40,
    ),
    _PatternSpec(
        entity_type="AADHAAR",
        pattern=re.compile(r"\b(\d{4}[\s-]\d{4}[\s-]\d{4})(?![\s-]?\d)\b"),
        mask_token=PII_MASK_TOKENS["AADHAAR"],
        priority=41,
        ambiguous=True,
    ),
    _PatternSpec(
        entity_type="ACCOUNT",
        pattern=re.compile(
            r"(?:account|a/c|bank\s+account|account\s+number)\s*(?:number|no\.?|#)?\s*[:\-]?\s*(\d{8,18})\b",
            re.IGNORECASE,
        ),
        mask_token=PII_MASK_TOKENS["ACCOUNT"],
        priority=50,
    ),
    _PatternSpec(
        entity_type="TRANSACTION_ID",
        pattern=re.compile(
            r"(?:transaction|txn|reference|ref|payment\s+id)\s*[:\-#]?\s*([A-Z0-9-]{6,})\b",
            re.IGNORECASE,
        ),
        mask_token=PII_MASK_TOKENS["TRANSACTION_ID"],
        priority=60,
    ),
    _PatternSpec(
        entity_type="TRANSACTION_ID",
        pattern=re.compile(r"\b(TXN[A-Z0-9-]{6,})\b", re.IGNORECASE),
        mask_token=PII_MASK_TOKENS["TRANSACTION_ID"],
        priority=61,
    ),
    _PatternSpec(
        entity_type="TRANSACTION_ID",
        pattern=re.compile(r"\b(REF-\d{4}-\d{4,})\b", re.IGNORECASE),
        mask_token=PII_MASK_TOKENS["TRANSACTION_ID"],
        priority=62,
    ),
    _PatternSpec(
        entity_type="CARD",
        pattern=re.compile(
            r"(?:card\s+(?:ending\s+)?|ending\s+)((?:\d{4}[\s-]?){3}\d{4})\b",
            re.IGNORECASE,
        ),
        mask_token=PII_MASK_TOKENS["CARD"],
        priority=35,
    ),
    _PatternSpec(
        entity_type="CARD",
        pattern=re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"),
        mask_token=PII_MASK_TOKENS["CARD"],
        priority=71,
        ambiguous=True,
    ),
    _PatternSpec(
        entity_type="PAN",
        pattern=re.compile(
            r"(?:PAN|permanent\s+account\s+number)\s*[:\-#]?\s*([A-Z]{5}\d{4}[A-Z])\b",
            re.IGNORECASE,
        ),
        mask_token=PII_MASK_TOKENS["PAN"],
        priority=80,
    ),
    _PatternSpec(
        entity_type="PAN",
        pattern=re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b"),
        mask_token=PII_MASK_TOKENS["PAN"],
        priority=81,
        ambiguous=True,
    ),
)


@dataclass
class _CandidateMatch:
    entity_type: str
    start: int
    end: int
    mask_token: str
    priority: int
    ambiguous: bool


def _is_missing_text(value: object) -> bool:
    """Return True when text input is missing or blank."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and pd.isna(value):
        return True
    text = str(value).strip()
    return not text or text.lower() == "nan"


def _normalize_text(value: object) -> tuple[str | None, bool]:
    """Normalize input to a string or mark it missing."""
    if _is_missing_text(value):
        return None, True
    return str(value), False


def _empty_result(original: str | None, warning: str | None = None) -> PIIDetectionResult:
    return PIIDetectionResult(
        original_text=original,
        masked_text="",
        detected=False,
        entity_types=[],
        entities=[],
        warning=warning,
        review_required=False,
    )


def _match_span(spec: _PatternSpec, text: str) -> list[_CandidateMatch]:
    matches: list[_CandidateMatch] = []
    for found in spec.pattern.finditer(text):
        if found.lastindex:
            start, end = found.start(1), found.end(1)
        else:
            start, end = found.start(), found.end()
        matches.append(
            _CandidateMatch(
                entity_type=spec.entity_type,
                start=start,
                end=end,
                mask_token=spec.mask_token,
                priority=spec.priority,
                ambiguous=spec.ambiguous,
            )
        )
    return matches


def _overlaps(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
    return any(not (end <= occ_start or start >= occ_end) for occ_start, occ_end in occupied)


def _resolve_matches(candidates: list[_CandidateMatch]) -> list[_CandidateMatch]:
    """Resolve overlapping detections using priority and span position."""
    ordered = sorted(candidates, key=lambda item: (item.priority, item.start, -(item.end - item.start)))
    selected: list[_CandidateMatch] = []
    occupied: list[tuple[int, int]] = []

    for candidate in ordered:
        if _overlaps(candidate.start, candidate.end, occupied):
            continue
        selected.append(candidate)
        occupied.append((candidate.start, candidate.end))

    return sorted(selected, key=lambda item: (item.start, item.priority))


def _collect_candidates(text: str) -> tuple[list[_CandidateMatch], set[tuple[int, int]]]:
    """Collect entity candidates with UPI detected before email."""
    all_candidates: list[_CandidateMatch] = []
    upi_spans: set[tuple[int, int]] = set()

    for spec in PII_PATTERN_SPECS:
        if spec.entity_type == "UPI":
            for match in _match_span(spec, text):
                all_candidates.append(match)
                upi_spans.add((match.start, match.end))

    for spec in PII_PATTERN_SPECS:
        if spec.entity_type == "EMAIL":
            for match in _match_span(spec, text):
                if any(not (match.end <= s or match.start >= e) for s, e in upi_spans):
                    continue
                all_candidates.append(match)
        elif spec.entity_type != "UPI":
            all_candidates.extend(_match_span(spec, text))

    return all_candidates, upi_spans


def _build_entities(matches: list[_CandidateMatch]) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    for match in matches:
        entities.append(
            PIIEntity(
                entity_type=match.entity_type,
                start=match.start,
                end=match.end,
                original_length=match.end - match.start,
                masked_value=match.mask_token,
            )
        )
    return entities


def _apply_masks(text: str, entities: list[PIIEntity]) -> str:
    masked = text
    for entity in sorted(entities, key=lambda item: item.start, reverse=True):
        masked = masked[: entity.start] + entity.masked_value + masked[entity.end :]
    return masked


def _needs_review(matches: list[_CandidateMatch]) -> bool:
    if not matches:
        return False
    if any(match.ambiguous for match in matches):
        return True
    if len({match.entity_type for match in matches}) > 1:
        return True
    return False


def detect_pii(text: str | None) -> PIIDetectionResult:
    """Detect PII entities in feedback text without modifying the original string."""
    normalized, missing = _normalize_text(text)
    if missing:
        return _empty_result(None if text is None or (isinstance(text, float) and pd.isna(text)) else "", MISSING_TEXT_WARNING)

    assert normalized is not None
    candidates, _ = _collect_candidates(normalized)
    resolved = _resolve_matches(candidates)
    entities = _build_entities(resolved)
    entity_types = sorted({entity.entity_type for entity in entities})

    return PIIDetectionResult(
        original_text=normalized,
        masked_text=_apply_masks(normalized, entities) if entities else normalized,
        detected=bool(entities),
        entity_types=entity_types,
        entities=entities,
        warning=None,
        review_required=_needs_review(resolved),
    )


def mask_pii(text: str | None) -> str:
    """Return masked feedback text, or an empty string when input is missing."""
    return detect_and_mask_pii(text).masked_text


def detect_and_mask_pii(text: str | None) -> PIIDetectionResult:
    """Detect PII and return a full masking result."""
    return detect_pii(text)


def mask_dataframe_feedback(
    df: pd.DataFrame,
    text_column: str = "feedback_text",
) -> pd.DataFrame:
    """Add original/masked text columns and PII metadata to a feedback DataFrame."""
    if text_column not in df.columns:
        raise KeyError(f"Text column '{text_column}' was not found in the DataFrame.")

    output = df.copy()
    originals: list[str | None] = []
    masked_values: list[str] = []
    detected_flags: list[bool] = []
    entity_type_lists: list[list[str]] = []
    review_flags: list[bool] = []

    for value in output[text_column].tolist():
        result = detect_and_mask_pii(value)
        originals.append(result.original_text)
        masked_values.append(result.masked_text)
        detected_flags.append(result.detected)
        entity_type_lists.append(result.entity_types)
        review_flags.append(result.review_required)

    output["original_text"] = originals
    output["masked_text"] = masked_values
    output["pii_detected"] = detected_flags
    output["pii_entity_types"] = entity_type_lists
    output["pii_review_required"] = review_flags
    return output
