"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


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

    Returns a relevance-sorted list of matching listing dicts, or [] if nothing
    matches. Never raises an exception.
    """
    listings = load_listings()

    # Filter by price and size
    candidates = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None:
            item_size = (item.get("size") or "").lower()
            if size.lower() not in item_size:
                continue
        candidates.append(item)

    if not candidates:
        return []

    # Score by keyword overlap across all text fields
    keywords = description.lower().split()

    def score(item: dict) -> int:
        text_parts = [
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            item.get("brand", "") or "",
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
        ]
        blob = " ".join(text_parts).lower()
        return sum(1 for kw in keywords if kw in blob)

    scored = [(score(item), item) for item in candidates]
    scored = [(s, item) for s, item in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Handles empty wardrobe by giving general styling advice. Never raises an
    exception or returns an empty string.
    """
    try:
        client = _get_groq_client()
        items = wardrobe.get("items", [])

        if not items:
            prompt = (
                f"A user just found this secondhand item:\n"
                f"Item: {new_item['title']}\n"
                f"Category: {new_item['category']}\n"
                f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
                f"Colors: {', '.join(new_item.get('colors', []))}\n"
                f"Condition: {new_item.get('condition', 'good')}\n\n"
                f"The user has no wardrobe on file yet. Give 1–2 practical styling suggestions: "
                f"what types of bottoms, tops, shoes, or layers pair well with this item, "
                f"and what overall vibe or aesthetic does it suit? Be specific and casual in tone."
            )
        else:
            wardrobe_lines = "\n".join(
                f"- {w['name']} ({w['category']}, colors: {', '.join(w.get('colors', []))})"
                for w in items
            )
            prompt = (
                f"A user is considering buying this secondhand item:\n"
                f"Item: {new_item['title']}\n"
                f"Category: {new_item['category']}\n"
                f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
                f"Colors: {', '.join(new_item.get('colors', []))}\n\n"
                f"Their current wardrobe:\n{wardrobe_lines}\n\n"
                f"Suggest 1–2 complete outfit combinations that incorporate this new item "
                f"with pieces from their wardrobe. Reference the wardrobe pieces by name. "
                f"Be specific, practical, and casual in tone."
            )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=400,
        )
        result = response.choices[0].message.content.strip()
        if result:
            return result
    except Exception:
        pass

    category = new_item.get("category", "item")
    return (
        f"Couldn't generate a full outfit suggestion right now, but this {category} "
        f"pairs well with basics in a similar color palette."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Returns a 2–4 sentence casual social-media caption. If outfit is empty,
    returns an error message string. Never raises an exception.
    """
    if not outfit or not outfit.strip():
        return "Can't create a fit card without an outfit description."

    title = new_item.get("title", "this find")
    price = new_item.get("price", "")
    platform = new_item.get("platform", "a thrift app")
    price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok OOTD caption for this outfit. "
        f"Make it casual, authentic, and specific — like a real post, not a product description.\n\n"
        f"Thrifted item: {title} — {price_str} from {platform}\n"
        f"Outfit: {outfit}\n\n"
        f"Rules:\n"
        f"- Mention the item name, price ({price_str}), and platform ({platform}) once each\n"
        f"- Use lowercase, conversational tone\n"
        f"- Capture the specific vibe of the outfit\n"
        f"- No hashtags\n"
        f"Return only the caption text."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.2,
            max_tokens=200,
        )
        result = response.choices[0].message.content.strip()
        if result:
            return result
    except Exception:
        pass

    return "Fit card unavailable right now — but trust, this look is worth sharing."
