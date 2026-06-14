# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Describe what you're looking for in plain English — FitFindr searches mock thrift listings, suggests outfit combinations using your wardrobe, and generates a shareable fit card caption.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Open the URL shown in the terminal (usually `http://127.0.0.1:7860`).

Run tests:
```bash
pytest tests/
```

---

## Tool Inventory

### `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

Loads all 40 mock listings and filters them by price ceiling and size (if provided), then scores each surviving listing by keyword overlap with the description across title, description, category, style_tags, colors, and brand. Returns a list of matching listing dicts sorted by relevance score, highest first. Returns an empty list if nothing matches — never raises an exception.

Each returned dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

### `suggest_outfit(new_item: dict, wardrobe: dict) → str`

Given the thrifted item the user is considering and their current wardrobe, calls the Groq LLM (`llama-3.3-70b-versatile`) to suggest 1–2 complete outfit combinations. If the wardrobe is empty, the prompt asks for general styling advice instead of named pairings. Returns a non-empty string — never raises an exception.

### `create_fit_card(outfit: str, new_item: dict) → str`

Calls the Groq LLM at temperature 1.2 to generate a 2–4 sentence casual social-media caption (Instagram/TikTok OOTD style) built around the thrifted find. Mentions the item name, price, and platform once each. Outputs vary across calls for the same input due to higher temperature. Returns a descriptive error message string if `outfit` is empty — never raises an exception.

---

## How the Planning Loop Works

The planning loop lives in `run_agent()` in `agent.py`. It runs a fixed conditional sequence — not all tools unconditionally, but branching on what each step returns.

**Step 1 — Parse the query.** Regex extracts three parameters from the natural language query:
- `description`: everything remaining after price and size phrases are removed
- `size`: matched by `size\s+(\S+)` or standalone size tokens like `M`, `XL`
- `max_price`: matched by `under\s*\$?(\d+)` and similar patterns

**Step 2 — Search.** `search_listings()` is called with the parsed parameters. The result is checked immediately:
- **If empty:** `session["error"]` is set to a message telling the user what was searched and what to try differently. The function returns the session right here. `suggest_outfit` and `create_fit_card` are never called.
- **If results found:** `session["selected_item"]` is set to `results[0]` and the loop continues.

**Step 3 — Suggest outfit.** `suggest_outfit()` is called with the selected item and the user's wardrobe. Result stored in `session["outfit_suggestion"]`.

**Step 4 — Fit card.** `create_fit_card()` is called with the outfit suggestion and selected item. Result stored in `session["fit_card"]`.

**Step 5 — Return.** The completed session dict is returned to `app.py`, which maps the fields to the three Gradio output panels.

The only branch point is after search. All other tools always run if a listing is found, because there is no useful partial output without all three.

---

## State Management

All state lives in a single `session` dict initialized by `_new_session()` at the start of each call to `run_agent()`. Tools do not share state directly — they receive inputs as arguments and their outputs are written into the session immediately after returning.

| Session key | Set after | Used by |
|---|---|---|
| `session["parsed"]` | Query parsing | `search_listings()` args |
| `session["search_results"]` | `search_listings()` | Selecting `selected_item` |
| `session["selected_item"]` | Top result selection | `suggest_outfit()`, `create_fit_card()` |
| `session["wardrobe"]` | Session init | `suggest_outfit()` |
| `session["outfit_suggestion"]` | `suggest_outfit()` | `create_fit_card()` |
| `session["fit_card"]` | `create_fit_card()` | Returned to UI |
| `session["error"]` | Search failure | Checked in `app.py` before rendering |

The session is returned from `run_agent()` and unpacked in `handle_query()` in `app.py` to populate the three output panels. No global state — each call to `run_agent()` gets a fresh session.

---

## Error Handling

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | No listings match the query | Sets `session["error"]` to `"No listings found for '[query]'. Try broader keywords, remove the size filter, or raise your price limit."` Returns the session immediately — `suggest_outfit` and `create_fit_card` are never called. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe['items'] == []`) | Switches to a general-styling LLM prompt instead of a wardrobe-pairing prompt. Returns general advice string. Never crashes or returns empty. |
| `create_fit_card` | `outfit` argument is empty or whitespace-only | Returns `"Can't create a fit card without an outfit description."` immediately without calling the LLM. |

**Concrete example — no results:**

Query: `"designer ballgown size XXS under $5"`

`search_listings` returned `[]`. The agent set `session["error"]` and returned immediately. `suggest_outfit` and `create_fit_card` were never called. The UI showed the error in the first panel; the other two panels were blank.

**Concrete example — empty wardrobe:**

Running `suggest_outfit(item, get_empty_wardrobe())` with `wardrobe["items"] == []` produced general styling advice — the LLM was given a prompt asking what types of pieces and aesthetics pair well with the item rather than referencing named wardrobe pieces. No exception was raised and the string was non-empty.

---

## Spec Reflection

**One way planning.md helped:** Writing out the state management table before touching `agent.py` made the implementation straightforward — I already knew exactly which key to write after each tool call and which keys to read as arguments to the next. There was no ambiguity about where data lived.

**One way implementation diverged from the spec:** The planning.md described parsing size tokens like `S`, `M`, `L` as standalone regex matches in a single expression. In practice, Python's ternary operator precedence inside the `or` chain caused size to silently return `None` even when matched. The fix required restructuring into a multi-line `if/else` block. The spec described the intent correctly; the code needed a different shape to express it reliably.

---

## AI Usage

**Instance 1 — `search_listings` implementation:**
I gave Claude the Tool 1 spec block from `planning.md` (inputs with types, return value with field list, failure mode, and the scoring strategy) and asked it to implement the function using `load_listings()`. The generated code filtered correctly by price and size but scored only against `title` and `style_tags`. I revised it to also score against `description`, `category`, `colors`, and `brand` to match the spec's intent of keyword overlap across all text fields. I verified by confirming that a query for "graphic tee" surfaced results where the keyword appeared in the description field rather than the title alone.

**Instance 2 — planning loop in `agent.py`:**
I gave Claude the full Planning Loop section, State Management table, and Architecture diagram from `planning.md` and asked it to implement `run_agent()`. The generated code called all three tools unconditionally — it checked `if not results` but only printed a warning rather than returning early. I overrode this to match the spec: set `session["error"]` and `return session` immediately when search returns empty, so `suggest_outfit` is never called with empty input. I verified by running the no-results path and confirming `session["fit_card"]` was `None`.
