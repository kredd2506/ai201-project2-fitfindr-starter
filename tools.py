"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Groq-hosted chat model used by the LLM tools. Swap here if needed.
GROQ_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Tokenize the description into lowercase keywords (ignore tiny words).
    keywords = [w for w in re.findall(r"[a-z0-9]+", description.lower()) if len(w) > 2]

    results = []
    for item in listings:
        # Filter: price ceiling.
        if max_price is not None and item["price"] > max_price:
            continue

        # Filter: size (case-insensitive substring match, e.g. "M" in "S/M").
        if size is not None and size.lower() not in item["size"].lower():
            continue

        # Score: keyword overlap against the searchable text. style_tags and
        # title are the strongest signals, so weight them higher.
        tags = " ".join(item["style_tags"]).lower()
        title = item["title"].lower()
        body = f"{item['description']} {item['category']}".lower()

        score = 0
        for kw in keywords:
            if kw in tags:
                score += 3
            elif kw in title:
                score += 2
            elif kw in body:
                score += 1

        # Drop listings with no keyword overlap at all.
        if score > 0:
            results.append((score, item))

    # Sort by score, highest first, and return just the listing dicts.
    results.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_line = (
        f"{new_item['title']} — {new_item['category']}, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])}"
    )

    items = wardrobe.get("items", [])

    if not items:
        # Empty wardrobe: general styling advice, not an error.
        prompt = (
            "A user is considering buying this secondhand item:\n"
            f"  {item_line}\n\n"
            "They haven't added any wardrobe items yet. Give friendly, general "
            "styling advice for this piece: what kinds of items pair well with it, "
            "what vibe it suits, and how they might wear it. 2-4 sentences. "
            "Start by noting they can add wardrobe items for personalized pairings."
        )
    else:
        # Format the wardrobe so the model can name specific pieces.
        wardrobe_lines = "\n".join(
            f"  - {w['name']} ({w['category']}, {', '.join(w['colors'])})"
            for w in items
        )
        prompt = (
            "A user is considering buying this secondhand item:\n"
            f"  {item_line}\n\n"
            "Here is their current wardrobe:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with specific, "
            "named pieces from their wardrobe. Refer to the wardrobe pieces by name. "
            "Keep it concise and practical."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        # Don't raise — let the pipeline continue to the fit card.
        return f"(Styling suggestions are temporarily unavailable: {exc})"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Guard: no usable outfit → return a descriptive string, never raise.
    if not outfit or not outfit.strip():
        return (
            f"Couldn't generate a fit card — no outfit was available for "
            f"{new_item['title']}. Here's the listing on its own: "
            f"{new_item['title']}, ${new_item['price']:.2f} on {new_item['platform']}."
        )

    prompt = (
        "Write a short, casual outfit caption (like a real OOTD post on "
        "Instagram or TikTok — not a product description) for this thrifted find.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']:.2f}\n"
        f"Platform: {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        "Requirements: 2-4 sentences. Mention the item name, price, and platform "
        "naturally, once each. Capture the vibe in specific terms. Keep it authentic "
        "and a little playful."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,  # higher temp so captions vary between runs
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return (
            f"{new_item['title']} — ${new_item['price']:.2f} on "
            f"{new_item['platform']}. (Caption generation unavailable: {exc})"
        )
