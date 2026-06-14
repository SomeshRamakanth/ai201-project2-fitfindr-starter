# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Loads all mock listings and filters them by price ceiling and size (if provided), then scores each surviving listing by keyword overlap with the user's description across title, description, category, style_tags, colors, and brand. Returns a relevance-sorted list of matching listings, or an empty list if nothing scores above zero.

**Input parameters:**
- `description` (str): Free-text keywords describing the item the user wants (e.g., "vintage graphic tee"). Used for keyword scoring across all text fields.
- `size` (str | None): Size string to filter by (e.g., "M", "W30"). Case-insensitive substring match. If None, no size filtering is applied.
- `max_price` (float | None): Maximum price (inclusive). Listings with price > max_price are excluded. If None, no price filtering is applied.

**What it returns:**
A `list[dict]` of matching listing dicts, sorted by relevance score (highest first). Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str). Returns `[]` if no listings match — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to: `"No listings found for '[description]'[size/price context]. Try broader keywords, a different size, or a higher price limit."` and returns the session immediately without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given the thrifted item the user is considering and their current wardrobe, uses the Groq LLM to suggest 1–2 complete outfit combinations. If the wardrobe is empty, provides general styling advice for the item type rather than named pairings.

**Input parameters:**
- `new_item` (dict): The listing dict for the item being considered (the top result from search_listings).
- `wardrobe` (dict): A wardrobe dict with key `'items'` → `list[dict]`. Each wardrobe item has: `id`, `name`, `category`, `colors`, `style_tags`, `notes`. May be an empty list.

**What it returns:**
A non-empty `str` with 1–2 outfit suggestions. If wardrobe is populated, suggestions reference specific wardrobe pieces by name. If wardrobe is empty, suggestions describe the kinds of items and styling approaches that would work well with the new item.

**What happens if it fails or returns nothing:**
If the LLM call fails or returns an empty string, the function returns a fallback string: `"Couldn't generate a full outfit suggestion right now, but this [item category] pairs well with basics in a similar color palette."` — never raises an exception.

---

### Tool 3: create_fit_card

**What it does:**
Uses the Groq LLM at higher temperature to generate a 2–4 sentence casual social-media caption (Instagram/TikTok OOTD style) describing the outfit built around the thrifted find. Outputs vary across calls for the same input.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from suggest_outfit.
- `new_item` (dict): The listing dict for the thrifted item — used to pull title, price, and platform for the caption.

**What it returns:**
A `str` of 2–4 casual sentences usable as a social-media caption. Mentions the item name, price, and platform once each. Sounds authentic, not like a product description. Returns a descriptive error message string if `outfit` is empty or whitespace — never raises an exception.

**What happens if it fails or returns nothing:**
If `outfit` is empty/whitespace, returns: `"Can't create a fit card without an outfit description."`. If the LLM call fails, returns: `"Fit card unavailable right now — but trust, this look is worth sharing."`.

---

### Additional Tools (if any)

None for the base implementation.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop runs in `run_agent()` and follows this conditional sequence:

1. **Initialize session** via `_new_session(query, wardrobe)`.

2. **Parse the query** using regex to extract:
   - `description`: everything before size/price keywords (fallback: entire query)
   - `size`: matched by pattern `size\s+(\S+)` or `\b([SMLX]+\d*)\b`
   - `max_price`: matched by pattern `under\s+\$?(\d+\.?\d*)` or `\$(\d+\.?\d*)\s+or\s+less`
   Store in `session["parsed"]`.

3. **Call search_listings** with parsed parameters. Store result in `session["search_results"]`.
   - **Branch — empty results:** set `session["error"]` to a helpful message (what the user searched for + suggestion to loosen filters). Return session immediately. `suggest_outfit` and `create_fit_card` are NOT called.
   - **Branch — results found:** set `session["selected_item"] = session["search_results"][0]`. Continue.

4. **Call suggest_outfit** with `(session["selected_item"], session["wardrobe"])`. Store result in `session["outfit_suggestion"]`.

5. **Call create_fit_card** with `(session["outfit_suggestion"], session["selected_item"])`. Store result in `session["fit_card"]`.

6. **Return session.** `session["error"]` is None on success.

The agent only deviates from the happy path at step 3 — all other tools always run if a listing is found, because there is no useful partial output without all three.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in the `session` dict created by `_new_session()` at the start of each interaction. Tools do not share state directly — they receive their inputs as arguments and write their outputs into the session dict immediately after returning.

| Session key | Written after | Read by |
|---|---|---|
| `session["parsed"]` | Step 2 (parse) | Step 3 (search_listings args) |
| `session["search_results"]` | Step 3 (search_listings) | Step 4 (selected_item selection) |
| `session["selected_item"]` | Step 4 | Step 5 (suggest_outfit), Step 6 (create_fit_card) |
| `session["wardrobe"]` | Step 1 (init) | Step 5 (suggest_outfit) |
| `session["outfit_suggestion"]` | Step 5 (suggest_outfit) | Step 6 (create_fit_card) |
| `session["fit_card"]` | Step 6 (create_fit_card) | Returned to UI |
| `session["error"]` | Step 3 on failure | Checked in app.py before rendering |

The session is returned from `run_agent()` and unpacked by `handle_query()` in app.py to populate the three Gradio output panels.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match (empty list returned) | Sets `session["error"]` to `"No listings found for '[query]'. Try broader keywords, remove the size filter, or raise your price limit."` — returns session early, skips the other two tools |
| suggest_outfit | Wardrobe is empty (`wardrobe['items'] == []`) | Calls LLM with a general-styling prompt instead of a wardrobe-pairing prompt — returns general advice string, never crashes or returns empty |
| create_fit_card | `outfit` argument is empty or whitespace-only | Returns `"Can't create a fit card without an outfit description."` immediately without calling the LLM |

---

## Architecture

```
User query (natural language)
        │
        ▼
  [Parse query]  ──────────────────────────────────────────────┐
  regex extracts description / size / max_price                │
  → session["parsed"]                                          │
        │                                                      │
        ▼                                                      │
  [search_listings(description, size, max_price)]              │
  loads + filters + scores listings                            │
  → session["search_results"]                                  │
        │                                                      │
        ├─ results == [] ──► session["error"] = "No listings"  │
        │                    RETURN SESSION EARLY ─────────────┘
        │
        │ results found
        ▼
  session["selected_item"] = results[0]
        │
        ▼
  [suggest_outfit(selected_item, wardrobe)]
  LLM call — wardrobe-paired or general styling
  → session["outfit_suggestion"]
        │
        ▼
  [create_fit_card(outfit_suggestion, selected_item)]
  LLM call (higher temperature) — OOTD caption
  → session["fit_card"]
        │
        ▼
  RETURN session  →  app.py maps to 3 Gradio output panels
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **Tool: search_listings** — I gave Claude the Tool 1 spec block (inputs, return value, failure mode, scoring strategy) from this file and asked it to implement the function using `load_listings()` from the data loader. I verified the generated code filters by all three parameters and handles the empty-results case by checking that the function returns `[]` when given an impossible query. I tested with three queries: a matching query, a query with a strict price, and an impossible query.

- **Tool: suggest_outfit** — I gave Claude the Tool 2 spec block plus the `wardrobe_schema.json` structure. I asked it to implement the function using `groq.chat.completions.create` with the `llama-3.3-70b-versatile` model. I verified it branches on `wardrobe['items']` being empty and tested with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

- **Tool: create_fit_card** — I gave Claude the Tool 3 spec block and asked it to guard against empty outfit strings and use temperature 1.2 for variation. I ran it three times on the same input and confirmed the outputs differed.

**Milestone 4 — Planning loop and state management:**

I gave Claude the full Planning Loop section, State Management section, and the Architecture diagram above. I asked it to implement `run_agent()` in agent.py, verifying the generated code branches on empty search results and stores each tool output in the session dict before passing it to the next tool. I tested the no-results path with `"designer ballgown size XXS under $5"` and confirmed `session["error"]` is set and `session["fit_card"]` is None.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query. Regex extracts `description = "vintage graphic tee"`, `size = None` (none specified), `max_price = 30.0`. Stores in `session["parsed"]`.

**Step 2:**
`search_listings("vintage graphic tee", size=None, max_price=30.0)` is called. It loads 40 listings, filters to those priced ≤ $30, then scores each by keyword overlap with "vintage graphic tee" across title, description, style_tags, category, colors, brand. Returns a sorted list — e.g., `[{"id": "lst_002", "title": "Y2K Baby Tee Butterfly Print", "price": 18.0, "platform": "depop", ...}, ...]`. Stored in `session["search_results"]`. Because results is non-empty, `session["selected_item"] = results[0]`.

**Step 3:**
`suggest_outfit(selected_item, wardrobe)` is called with the Y2K tee dict and the user's 10-item example wardrobe. The LLM receives a prompt listing the new item's details and all wardrobe pieces and returns: `"Pair this butterfly tee with your baggy straight-leg jeans and chunky white sneakers for a classic Y2K look — tuck the front corner slightly for shape. Alternatively, layer it under your vintage black denim jacket with wide-leg khakis and combat boots for a grungier feel."` Stored in `session["outfit_suggestion"]`.

**Step 4:**
`create_fit_card(outfit_suggestion, selected_item)` is called. The LLM writes a caption at temperature 1.2: `"thrifted this y2k butterfly tee off depop for $18 and my wide-legs have never been happier 🦋 tucked the front corner and added my chunky sneaks — full look basically styled itself"`. Stored in `session["fit_card"]`.

**Final output to user:**
- Panel 1 (listing): `"Y2K Baby Tee Butterfly Print — $18.00 | depop | Size: OS | Condition: excellent"`
- Panel 2 (outfit idea): The suggest_outfit string above.
- Panel 3 (fit card): The create_fit_card caption above.
