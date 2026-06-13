# FitFindr 🛍️

FitFindr is an agentic secondhand-shopping assistant. You describe what you're
looking for in plain language; it searches a catalog of mock secondhand
listings, styles the best match against your existing wardrobe, and writes a
short, shareable "fit card" caption for the find — all driven by a planning loop
that decides what to do based on what each step returns.

---

## Setup

```bash
# 1. Create and activate a virtual environment (Python 3.10+ recommended)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Groq API key (free key at https://console.groq.com)
echo "GROQ_API_KEY=your_key_here" > .env
```

### Run the web app
```bash
python app.py
```
Open the URL printed in the terminal (usually `http://127.0.0.1:7860`).

### Run the agent from the command line
```bash
python agent.py        # runs a happy-path query and a no-results query
```

### Run the tests
```bash
pytest tests/
```

---

## Architecture at a glance

```
User query + wardrobe → run_agent() → search_listings → suggest_outfit → create_fit_card → session
                                            │ (empty)
                                            └─► error set, return early (LLM tools skipped)
```

`app.py` (Gradio UI) → `agent.py` (planning loop + state) → `tools.py` (the three tools)
→ `utils/data_loader.py` (loads listings + wardrobe). The LLM tools use Groq
(`llama-3.3-70b-versatile`).

---

## Tool Inventory

### 1. `search_listings(description, size=None, max_price=None) -> list[dict]`
- **Purpose:** Find catalog listings matching the user's request and rank them by
  relevance. Pure Python (no LLM) — deterministic and testable.
- **Inputs:**
  - `description` (`str`): keywords describing the wanted item, e.g. `"vintage graphic tee"`.
  - `size` (`str | None`): size to filter by; case-insensitive substring match (e.g. `"M"` matches `"S/M"`). `None` skips size filtering.
  - `max_price` (`float | None`): inclusive price ceiling. `None` skips price filtering.
- **Output:** `list[dict]` of matching listings, sorted by relevance score (best
  first). Each dict has `id, title, description, category, style_tags, size,
  condition, price, colors, brand, platform`. Returns `[]` when nothing matches.

### 2. `suggest_outfit(new_item, wardrobe) -> str`
- **Purpose:** Suggest 1–2 concrete outfits pairing the selected listing with the
  user's existing wardrobe pieces (or general advice if the wardrobe is empty).
- **Inputs:**
  - `new_item` (`dict`): the selected listing dict from `search_listings`.
  - `wardrobe` (`dict`): a wardrobe with an `items` key holding a list of items, each `{id, name, category, colors, style_tags, notes}`. May be empty.
- **Output:** a non-empty `str`. With wardrobe items, it names specific owned
  pieces; with an empty wardrobe, it returns general styling advice.

### 3. `create_fit_card(outfit, new_item) -> str`
- **Purpose:** Turn the outfit suggestion + item details into a short, casual
  OOTD-style caption (2–4 sentences, higher temperature so it varies each run).
- **Inputs:**
  - `outfit` (`str`): the suggestion string from `suggest_outfit`.
  - `new_item` (`dict`): the selected listing dict (used for name, price, platform).
- **Output:** a `str` caption mentioning the item name, price, and platform once
  each. If `outfit` is empty/whitespace, returns a descriptive fallback string
  instead.

---

## Planning Loop

`run_agent(query, wardrobe)` in `agent.py` runs a fixed three-stage pipeline with
one conditional branch — it does **not** call all three tools unconditionally:

1. Create a fresh `session` via `_new_session(query, wardrobe)`.
2. **Parse** the query with `_parse_query()` into `{description, size, max_price}`
   (rule-based: a regex pulls a price after "under/$/less than", an explicit
   "size X" mention sets the size, and the leftover text becomes the description).
3. Call `search_listings(**parsed)` and store the result in `session["search_results"]`.
   - **If the list is empty:** set `session["error"]` to an informative message and
     **return immediately** — `suggest_outfit` and `create_fit_card` are never called.
   - **If non-empty:** continue.
4. Set `session["selected_item"] = search_results[0]` (top-ranked match).
5. Call `suggest_outfit(selected_item, wardrobe)` → `session["outfit_suggestion"]`.
6. Call `create_fit_card(outfit_suggestion, selected_item)` → `session["fit_card"]`.
7. Return the `session`.

The loop terminates either at step 3 (early return with `error` set) or after
step 6 (full success, `error` stays `None`). Because the path depends on what
`search_listings` returns, **the agent behaves differently for different inputs**:
"vintage graphic tee under $30" resolves to `lst_002`; "90s track jacket in size M"
resolves to `lst_004`; an impossible query exits early with only an error.

---

## State Management

A single `session` dict (created by `_new_session`) is the one source of truth
for an interaction. Tools never call each other directly — each stage **reads**
the previous stage's output from the session and **writes** its own result back:

| Key | Written by | Consumed by |
|-----|-----------|-------------|
| `query` | entry point | (record) |
| `parsed` | parse step | `search_listings` |
| `search_results` | `search_listings` | step 4 selection |
| `selected_item` | step 4 | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | entry point | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | UI |
| `error` | loop (on early exit) | UI |

State flows forward as the *same* objects (verified by identity checks: the dict
in `session["selected_item"]` is the exact object passed into both `suggest_outfit`
and `create_fit_card`). Nothing is re-prompted or hardcoded between steps.

`app.py`'s `handle_query()` checks `session["error"]` first: if set, it shows the
message in panel 1 and leaves the other two empty; otherwise it formats
`selected_item`, `outfit_suggestion`, and `fit_card` into the three output panels.

---

## Error Handling (per tool, with tested examples)

Every failure mode returns a useful value instead of raising. Each was triggered
directly during testing.

| Tool | Failure mode | Behavior | Tested example |
|------|-------------|----------|----------------|
| `search_listings` | No listing matches | Returns `[]`; the loop sets `session["error"]` and returns early, skipping the LLM tools. | `search_listings('designer ballgown', size='XXS', max_price=5)` → `[]`. Full agent → error: *"No secondhand listings matched your search. Try different keywords, a higher price, or a different size."* |
| `suggest_outfit` | Empty wardrobe | Returns general styling advice (not an error) and notes the user can add items for personalized pairings. | `suggest_outfit(item, get_empty_wardrobe())` → *"…you can add other items to see personalized pairing suggestions… this top pairs well with high-waisted jeans, flowy skirts, or distressed denim shorts…"* (no exception) |
| `create_fit_card` | Empty/whitespace outfit | Returns a descriptive fallback string (and shows the listing on its own); short-circuits before any LLM call. | `create_fit_card('', item)` → *"Couldn't generate a fit card — no outfit was available for Y2K Baby Tee — Butterfly Print. Here's the listing on its own: Y2K Baby Tee — Butterfly Print, $18.00 on depop."* |
| LLM tools (Groq) | API error / timeout | Caught; returns a short fallback string so the pipeline still finishes. | n/a (defensive) |

A no-results run leaves `selected_item`, `outfit_suggestion`, and `fit_card` all
`None` — confirmed with a call-counting spy showing `suggest_outfit` and
`create_fit_card` were called **0 times**.

---

## Spec Reflection

- **What matched the plan:** The implementation follows the planning.md spec
  closely — the three tool signatures, the session keys, and the early-return
  branch on empty search results all came straight from the plan, which made the
  build mostly mechanical.
- **One design decision left open in the plan:** query parsing. I went with a
  rule-based regex parser (price + explicit "size X" + leftover keywords) rather
  than an LLM parse, because it's deterministic and keeps `search_listings`
  testable without API calls. The trade-off is that it's literal: a query like
  "90s track jacket in size M" leaves a stray "in" in the description (harmless —
  it's a stopword that matches nothing). An LLM parser would handle messier
  phrasing but adds cost and nondeterminism.
- **Testing the failure modes mattered most.** Each error path returns a *specific*
  message, not a generic "no results" — and triggering them directly (rather than
  assuming they worked) is what confirmed the agent recovers gracefully.
- **Possible next steps:** strip trailing prepositions from the parsed description;
  let the user pick which of several matches to style (currently always the top
  result); and surface the runner-up listings in the UI.

---

## AI Usage

I used Claude as the coding assistant, feeding it the relevant `planning.md`
sections one piece at a time and reviewing each output against the spec before
keeping it.

**Instance 1 — implementing `search_listings`.**
- *Input I gave it:* the Tool 1 spec block from `planning.md` (the
  `description`/`size`/`max_price` parameters, the sorted-`list[dict]` return, and
  the empty-list failure mode) plus the `tools.py` docstring, with the instruction
  to use `load_listings()` and not call the LLM.
- *What it produced:* a pure-Python function that filters by price and size, scores
  by keyword overlap, drops zero-score listings, and sorts by score.
- *What I changed/overrode:* the first version scored every field equally. I
  changed it to **weight `style_tags` (3) and `title` (2) above the description
  body (1)** so a query like "vintage graphic tee" surfaces tagged items first. I
  also added a minimum keyword length filter (`len(w) > 2`) so stopwords like "a"
  and "in" don't inflate scores.

**Instance 2 — implementing the planning loop (`run_agent`).**
- *Input I gave it:* the Planning Loop and State Management sections plus the ASCII
  Architecture diagram from `planning.md`, and the `_new_session` session keys from
  `agent.py`.
- *What it produced:* a `run_agent()` that initializes the session, parses the
  query, calls the three tools in order, and returns early with `session["error"]`
  set when `search_results` is empty.
- *What I changed/overrode:* the query parser was the part I most had to correct.
  An early version detected size by matching standalone letters (`S`/`M`/`L`),
  which wrongly matched the **"m" in "I'm"** in the example query. I overrode it to
  only accept an explicit **"size X"** mention, which fixed the parse for every
  example query while keeping it deterministic.

**Instance 3 — writing the tests.**
- *Input I gave it:* the Error Handling table from `planning.md` and the three tool
  signatures, asking for at least one test per failure mode.
- *What it produced:* pytest tests covering happy paths and the no-results /
  empty-wardrobe / empty-outfit failure modes.
- *What I changed/overrode:* the initial tests called the live Groq API for the LLM
  tools, which is slow and flaky. I overrode this to **stub the Groq client with
  `monkeypatch`** (the `fake_groq` fixture), so the suite runs offline and
  deterministically while still exercising the real failure branches.

---

## Project Layout
```
.
├── app.py                 # Gradio UI + handle_query()
├── agent.py               # run_agent() planning loop + _parse_query() + session state
├── tools.py               # search_listings, suggest_outfit, create_fit_card
├── utils/data_loader.py   # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── data/                  # listings.json (40 listings) + wardrobe_schema.json
├── tests/test_tools.py    # isolation tests for all three tools (incl. failure modes)
├── planning.md            # design doc: tools, planning loop, state, errors, diagram
└── requirements.txt
```
