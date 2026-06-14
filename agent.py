"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex patterns.
    """
    q = query.strip()

    # Extract max_price: "under $30", "$30 or less", "less than $30"
    price_match = re.search(
        r'(?:under|less than|below|max|up to)\s*\$?(\d+\.?\d*)'
        r'|\$(\d+\.?\d*)\s+or\s+less',
        q, re.IGNORECASE
    )
    max_price = None
    if price_match:
        raw = price_match.group(1) or price_match.group(2)
        max_price = float(raw)

    # Extract size: "size M", "size XL", standalone S/M/L/XL/XXS/XXL, "size 8"
    size_match = re.search(
        r'\bsize\s+([A-Za-z0-9/]+)\b'
        r'|\b(XXS|XS|S\b|M\b|L\b|XL|XXL|2XL|3XL)\b'
        r'|\bW(\d{2})\b',
        q, re.IGNORECASE
    )
    size = None
    if size_match:
        size = size_match.group(1) or size_match.group(2)
        if not size and size_match.group(3):
            size = "W" + size_match.group(3)
        if size:
            size = size.strip()

    # Description: remove price and size phrases, trim
    description = q
    description = re.sub(
        r'(?:under|less than|below|max|up to)\s*\$?\d+\.?\d*'
        r'|\$\d+\.?\d*\s+or\s+less',
        '', description, flags=re.IGNORECASE
    )
    description = re.sub(
        r'\bsize\s+[A-Za-z0-9/]+\b'
        r'|\b(?:XXS|XS|XL|XXL|2XL|3XL)\b',
        '', description, flags=re.IGNORECASE
    )
    description = re.sub(r'\s+', ' ', description).strip(" .,")

    return {
        "description": description or query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Returns the session dict. Check session["error"] first — if not None,
    the interaction ended early and outfit_suggestion / fit_card will be None.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)

    # Step 2: parse the query
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: search listings
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        parts = [f"'{parsed['description']}'"]
        if parsed["size"]:
            parts.append(f"size {parsed['size']}")
        if parsed["max_price"] is not None:
            parts.append(f"under ${parsed['max_price']:.0f}")
        detail = ", ".join(parts)
        session["error"] = (
            f"No listings found for {detail}. "
            f"Try broader keywords, remove the size filter, or raise your price limit."
        )
        return session

    # Step 4: select top result
    session["selected_item"] = results[0]

    # Step 5: suggest outfit
    outfit = suggest_outfit(results[0], wardrobe)
    session["outfit_suggestion"] = outfit

    # Step 6: create fit card
    fit_card = create_fit_card(outfit, results[0])
    session["fit_card"] = fit_card

    # Step 7: return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
