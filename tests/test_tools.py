"""
Isolation tests for the three FitFindr tools.

- search_listings is pure Python, so it's tested against the real dataset.
- suggest_outfit and create_fit_card call the Groq LLM, so the Groq client is
  stubbed (see the fake_groq fixture) to keep these tests offline, fast, and
  deterministic. The empty-input failure modes are still exercised for real.
"""

from types import SimpleNamespace

import pytest

from tools import search_listings, suggest_outfit, create_fit_card


# ── Tool 1: search_listings (real data, no LLM) ──────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: nothing matches → empty list, NOT an exception.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    # Every returned listing must respect the price ceiling.
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    # Every returned listing must match the requested size (case-insensitive).
    results = search_listings("jacket", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


# ── Stub the Groq client for the LLM tools ───────────────────────────────────

def _fake_create(**kwargs):
    """Mimic the shape of a Groq chat completion response."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="FAKE LLM OUTPUT"))]
    )


class _FakeClient:
    chat = SimpleNamespace(completions=SimpleNamespace(create=_fake_create))


@pytest.fixture
def fake_groq(monkeypatch):
    """Replace the real Groq client with an offline stub."""
    monkeypatch.setattr("tools._get_groq_client", lambda: _FakeClient())


ITEM = {
    "id": "lst_test",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "description": "Faded bootleg graphic tee.",
    "category": "tops",
    "style_tags": ["vintage", "graphic tee"],
    "size": "L",
    "condition": "good",
    "price": 24.0,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}


# ── Tool 2: suggest_outfit ───────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe(fake_groq):
    # Failure mode: empty wardrobe must not crash; returns a non-empty string.
    out = suggest_outfit(ITEM, {"items": []})
    assert isinstance(out, str)
    assert out.strip() != ""


def test_suggest_outfit_with_items(fake_groq):
    wardrobe = {
        "items": [
            {"id": "w_001", "name": "Baggy straight-leg jeans", "category": "bottoms",
             "colors": ["dark blue"], "style_tags": ["denim", "baggy"], "notes": None},
        ]
    }
    out = suggest_outfit(ITEM, wardrobe)
    assert isinstance(out, str)
    assert out.strip() != ""


# ── Tool 3: create_fit_card ──────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    # Failure mode: empty outfit → descriptive string, no exception, no LLM call.
    card = create_fit_card("", ITEM)
    assert isinstance(card, str)
    assert ITEM["title"] in card


def test_create_fit_card_whitespace_outfit():
    # Whitespace-only is also treated as empty.
    card = create_fit_card("   ", ITEM)
    assert isinstance(card, str)
    assert ITEM["title"] in card


def test_create_fit_card_valid(fake_groq):
    card = create_fit_card("Tee with baggy jeans and chunky sneakers.", ITEM)
    assert isinstance(card, str)
    assert card.strip() != ""
