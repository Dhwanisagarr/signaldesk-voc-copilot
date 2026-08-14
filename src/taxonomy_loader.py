"""Taxonomy preset loader for SignalDesk domain rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from src.analysis_config import THEME_RULES, ThemeRuleConfig

TAXONOMIES_DIR = Path(__file__).parent / "taxonomies"

SESSION_TAXONOMY: str = "selected_taxonomy"

TAXONOMY_PRESETS: dict[str, str] = {
    "fintech": "Fintech & Payments (Default)",
    "saas": "SaaS & B2B Software",
    "ecommerce": "E-Commerce & Retail",
    "general": "General Customer Support",
}


def load_taxonomy_preset(preset_key: str = "fintech") -> tuple[ThemeRuleConfig, ...]:
    """Load ThemeRuleConfig tuple for a given taxonomy preset key."""
    if preset_key == "fintech" or not preset_key:
        return THEME_RULES

    preset_path = TAXONOMIES_DIR / f"{preset_key}.json"
    if not preset_path.exists():
        return THEME_RULES

    try:
        data = json.loads(preset_path.read_bytes())
        rules = []
        for item in data:
            subthemes: Mapping[str, tuple[str, ...]] = {
                k: tuple(v) for k, v in item.get("subthemes", {}).items()
            }
            rule = ThemeRuleConfig(
                theme=item["theme"],
                keywords=tuple(item["keywords"]),
                phrases=tuple(item["phrases"]),
                product_area=item.get("product_area", "other"),
                default_severity=item.get("default_severity", "medium"),
                default_intent=item.get("default_intent", "complaint"),
                subthemes=subthemes,
                suggested_action_template=item.get("suggested_action_template", ""),
            )
            rules.append(rule)
        return tuple(rules) if rules else THEME_RULES
    except Exception:
        return THEME_RULES


def get_taxonomy_rules_by_name(preset_key: str = "fintech") -> dict[str, ThemeRuleConfig]:
    """Return dictionary mapping theme name to ThemeRuleConfig for preset."""
    rules = load_taxonomy_preset(preset_key)
    return {rule.theme: rule for rule in rules}
