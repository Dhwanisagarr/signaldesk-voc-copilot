"""Tests for taxonomy preset loader."""

from __future__ import annotations

from src.taxonomy_loader import TAXONOMY_PRESETS, get_taxonomy_rules_by_name, load_taxonomy_preset


def test_load_default_fintech_preset() -> None:
    rules = load_taxonomy_preset("fintech")
    assert len(rules) > 0
    theme_names = {r.theme for r in rules}
    assert "payment_failure" in theme_names
    assert "refund_delay" in theme_names


def test_load_saas_preset() -> None:
    rules = load_taxonomy_preset("saas")
    assert len(rules) > 0
    theme_names = {r.theme for r in rules}
    assert "billing_issue" in theme_names


def test_load_unknown_preset_fallback() -> None:
    rules = load_taxonomy_preset("non_existent_domain")
    assert len(rules) > 0
    theme_names = {r.theme for r in rules}
    assert "payment_failure" in theme_names


def test_get_taxonomy_rules_by_name() -> None:
    rules_map = get_taxonomy_rules_by_name("ecommerce")
    assert "shipping_delay" in rules_map
    assert rules_map["shipping_delay"].product_area == "logistics"


def test_taxonomy_presets_dictionary() -> None:
    assert "fintech" in TAXONOMY_PRESETS
    assert "saas" in TAXONOMY_PRESETS
    assert "ecommerce" in TAXONOMY_PRESETS
    assert "general" in TAXONOMY_PRESETS
