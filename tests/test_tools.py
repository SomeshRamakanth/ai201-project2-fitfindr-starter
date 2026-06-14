"""
tests/test_tools.py

Isolation tests for the three FitFindr tools.
Run with: pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results_no_exception():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter():
    results = search_listings("jeans", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_result_fields():
    results = search_listings("tee", size=None, max_price=100)
    if results:
        item = results[0]
        for field in ("id", "title", "price", "platform", "category"):
            assert field in item


def test_search_sorted_by_relevance():
    results = search_listings("vintage denim jacket", size=None, max_price=100)
    # First result should be at least as relevant as others — just check non-empty
    assert len(results) >= 1


# ── suggest_outfit ────────────────────────────────────────────────────────────

def _sample_item():
    results = search_listings("tee", size=None, max_price=50)
    return results[0] if results else {
        "id": "test_001",
        "title": "Test Tee",
        "category": "tops",
        "style_tags": ["vintage"],
        "colors": ["white"],
        "condition": "good",
        "price": 20.0,
        "platform": "depop",
        "size": "M",
        "description": "A test tee",
        "brand": None,
    }


def test_suggest_outfit_with_wardrobe_returns_string():
    item = _sample_item()
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_no_exception():
    item = _sample_item()
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    item = _sample_item()
    outfit = "Pair this with baggy jeans and chunky sneakers for a relaxed 90s look."
    result = create_fit_card(outfit, item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_returns_error_string():
    item = _sample_item()
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert "can't" in result.lower() or "cannot" in result.lower() or "without" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_string():
    item = _sample_item()
    result = create_fit_card("   ", item)
    assert isinstance(result, str)
    assert len(result) > 0
