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
Filters the 40 mock listings down to the ones matching the user's request, ranks them by how well they match the keywords, and returns the matches best-first. This is pure Python (no LLM), so it's deterministic and easy to test.

**Input parameters:**
- `description` (str): keywords describing the wanted item, e.g. `"vintage graphic tee"`. Required.
- `size` (str | None): size to filter by, matched case-insensitively as a substring (e.g. `"M"` matches `"S/M"`). `None` skips size filtering.
- `max_price` (float | None): inclusive maximum price. `None` skips price filtering.

**What it returns:**
A `list[dict]` of matching listings, sorted by relevance score (best match first). Each dict contains: `id, title, description, category, style_tags (list), size, condition, price (float), colors (list), brand, platform`. Returns an empty list when nothing matches — it never raises.

**What happens if it fails or returns nothing:**
It returns `[]`. The tool itself doesn't error; the planning loop detects the empty list, sets `session["error"]` to a friendly "no matches" message, and returns early without calling `suggest_outfit`.

---

### Tool 2: suggest_outfit

**What it does:**
Given the selected listing and the user's wardrobe, it asks the LLM (Groq) for 1–2 concrete outfit ideas that pair the new item with specific pieces the user already owns.

**Input parameters:**
- `new_item` (dict): the selected listing dict from `search_listings` (the item being considered).
- `wardrobe` (dict): a wardrobe dict with an `items` key holding a list of wardrobe items, each `{id, name, category, colors, style_tags, notes}`. May be empty.

**What it returns:**
A non-empty `str` of outfit suggestions. When the wardrobe has items, it names specific pieces (e.g. "pair with your baggy dark-wash jeans and chunky white sneakers"). When the wardrobe is empty, it returns general styling advice for the item instead.

**What happens if it fails or returns nothing:**
An empty wardrobe is handled inside the tool (general advice, not an error). If the LLM call itself errors, it returns a short fallback string rather than raising, so the loop can still produce a fit card.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion plus the item details into a short, casual OOTD-style caption (Instagram/TikTok vibe) of about 2–4 sentences, using a higher LLM temperature so it reads differently each time.

**Input parameters:**
- `outfit` (str): the outfit suggestion string returned by `suggest_outfit()`.
- `new_item` (dict): the selected listing dict, used for the item name, price, and platform.

**What it returns:**
A 2–4 sentence caption `str` that mentions the item name, price, and platform once each and captures the outfit's vibe.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace, it returns a descriptive error-message string (and can fall back to a minimal caption built from `new_item` alone) — it never raises, so the UI always has something to show.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
The loop is a fixed three-stage pipeline with one error branch — there's no retry or looping.

1. Initialize the session with `_new_session(query, wardrobe)`.
2. **Parse** the query into `{description, size, max_price}` and store it in `session["parsed"]`. I'll parse with simple Python: a regex pulls a price after "under/$" into `max_price` and a size token (S/M/L/XL or `W##`) into `size`; the leftover text becomes `description`. (LLM parsing is a possible upgrade, but rule-based keeps it deterministic and testable.)
3. Call `search_listings(**session["parsed"])` and store the result in `session["search_results"]`.
   - **If `search_results` is empty:** set `session["error"]` to a helpful "no matches" message and **return the session immediately** — do not call `suggest_outfit`.
   - **If it's non-empty:** continue.
4. Set `session["selected_item"] = session["search_results"][0]` (the top-ranked match).
5. Call `suggest_outfit(session["selected_item"], session["wardrobe"])` and store it in `session["outfit_suggestion"]`. (An empty wardrobe still returns advice, so no branch is needed here.)
6. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])` and store it in `session["fit_card"]`.
7. Return the session.

**How it knows it's done:** the loop ends either at step 3 (early return with `error` set) or after step 6 (full success, `error` stays `None`).

---

## State Management

**How does information from one tool get passed to the next?**
A single `session` dict (created by `_new_session` in `agent.py`) is the one source of truth for the whole interaction. Tools don't call each other directly — each stage reads the previous stage's output from the session and writes its own result back into it:

- `query` — the original user text.
- `parsed` — `{description, size, max_price}` from the parse step.
- `search_results` — the list returned by `search_listings`.
- `selected_item` — `search_results[0]`, the input to `suggest_outfit`.
- `wardrobe` — the wardrobe dict passed in at the start.
- `outfit_suggestion` — the string from `suggest_outfit`, the input to `create_fit_card`.
- `fit_card` — the caption from `create_fit_card`.
- `error` — `None` normally; set to a message when the loop exits early.

`error` is the cross-cutting signal: `app.py`'s `handle_query` checks it first — if set, it shows the message in panel 1 and leaves panels 2 & 3 empty; otherwise it formats `selected_item`, `outfit_suggestion`, and `fit_card` into the three panels.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Loop sets `session["error"]` and returns early. The message names the gap and offers a concrete next step, e.g. *"No secondhand listings matched 'designer ballgown size XXS under $5'. Try removing the price cap, widening the size, or using broader keywords like 'gown' or 'formal dress'."* Panels 2 & 3 stay empty. |
| suggest_outfit | Wardrobe is empty | Not treated as an error — the tool returns general styling advice for the item alone and the loop continues. The output is prefaced so the user knows why, e.g. *"You haven't added any wardrobe items yet, so here are general ways to style this piece…"* and suggests adding wardrobe items for personalized pairings. |
| create_fit_card | Outfit input is missing or incomplete | The tool returns a descriptive string instead of raising, e.g. *"Couldn't generate a fit card — no outfit was available for {title}. Here's the listing on its own: {title}, ${price} on {platform}."* The loop still returns a session so the UI shows the listing rather than a blank panel. |
| (LLM call in suggest_outfit / create_fit_card) | Groq API error or timeout | Catch the exception, return a short fallback string, don't raise. The user sees the listing plus a note that styling is temporarily unavailable, instead of a crash. |

---

## Architecture

```
User query + wardrobe
      │
      ▼
run_agent()  ──►  session = _new_session(query, wardrobe)
      │
      ├─► parse query ─────────────► session["parsed"] = {description, size, max_price}
      │
      ├─► search_listings(description, size, max_price)
      │        │ returns []                                   returns [item, ...]
      │        ├──► session["error"] = "No listings…"          │
      │        │     return session  ──► [ERROR EARLY EXIT] ◄──┘  (only when empty)
      │        ▼
      │   session["search_results"] = [...]
      │   session["selected_item"]  = search_results[0]
      │
      ├─► suggest_outfit(selected_item, wardrobe)
      │        │ (empty wardrobe → general advice, not an error)
      │        ▼
      │   session["outfit_suggestion"] = "..."
      │
      └─► create_fit_card(outfit_suggestion, selected_item)
               │ (empty outfit → error-message string, no raise)
               ▼
           session["fit_card"] = "..."
               │
               ▼
           return session ──► app.py handle_query() ──► 3 UI panels
                                 (listing · outfit · fit card)
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

Tool used throughout: Claude. For each tool I give it the matching spec section above as the prompt, state the acceptance checks before running anything, then verify with concrete test inputs.

- **search_listings** — Input: the *Tool 1* block (params, sorted-`list[dict]` return, empty-list failure mode) plus the instruction to use `load_listings()`. Expect: a pure-Python function that filters by `max_price` and `size`, scores by keyword overlap with `description`, drops score-0 items, and sorts highest-first. Verify: read the code to confirm it uses all three params, returns `[]` instead of raising, and doesn't call the LLM; then test 3 queries — `("vintage graphic tee", max_price=30)` → includes `lst_006`/`lst_002`; `("track jacket", size="M")` → includes `lst_004`; `("designer ballgown", max_price=5)` → `[]`.
- **suggest_outfit** — Input: the *Tool 2* block plus the wardrobe field list. Expect: a Groq call that names specific wardrobe pieces when items exist and gives general advice when empty, always returning a non-empty string. Verify: confirm it branches on `wardrobe["items"]` being empty; test with the example wardrobe (names real pieces) and with `get_empty_wardrobe()` (still returns advice, no crash).
- **create_fit_card** — Input: the *Tool 3* block plus the caption style rules. Expect: a Groq call returning a 2–4 sentence caption, guarding an empty `outfit`. Verify: confirm the empty-`outfit` guard and raised temperature; test a real outfit string (caption mentions item/price/platform) and `create_fit_card("", item)` (returns a string, doesn't raise).

**Milestone 4 — Planning loop and state management:**

Tool: Claude. Input: the *Planning Loop* branches + *State Management* section + the *Architecture* diagram above, plus the `_new_session` keys from `agent.py`. Expect: a `run_agent()` that initializes the session, parses the query, calls the three tools in order writing each result into its session key, and returns early with `session["error"]` set when `search_results` is empty. Verify: read the code to confirm the early-return branch and correct key assignments, then run `python agent.py` — the happy-path query prints a found item + outfit + fit card with `error` None, and the "designer ballgown size XXS under $5" query prints only the error message with `outfit_suggestion`/`fit_card` as `None`.




---

## What FitFindr needs to do (in my own words)
FitFindr takes a natural-language shopping request plus the user's wardrobe and runs it through three tools in sequence to return a recommendation. The user's query triggers `search_listings` first (it reads the style/size/price intent and then filters the 40 mock listings); the top match it returns then triggers `suggest_outfit`, which pairs that item against the user's wardrobe; finally the chosen outfit triggers `create_fit_card`, which formats everything into a clean summary for the UI.

On failure the loop degrades gracefully instead of crashing: if `search_listings` finds nothing it stops and tells the user that no matches were found, if the wardrobe is empty `suggest_outfit` skips the pairing and recommends the item on its own, and if the outfit data is incomplete `create_fit_card` falls back to showing just the listing as best it can.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
First, `search_listings` extracts the intent from the query (`description="vintage graphic tee"`, `max_price=30`, no size given). It filters `load_listings()` and matches `lst_006` ($24) and `lst_002` ($18). It returns the best match → **lst_006**.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
The `lst_006` result from Step 1 triggers `suggest_outfit`, called with `new_item=lst_006` and `wardrobe=get_example_wardrobe()`. It pairs the tee with compatible wardrobe pieces by category/color/style — e.g. `w_001` (baggy jeans) and `w_007` (chunky sneakers), which the user mentioned. It returns an outfit plus a short rationale.

**Step 3:**
<!-- Continue until the full interaction is complete -->
The outfit from Step 2 triggers `create_fit_card`. It formats the listing + paired items + rationale into a readable fit-card string. If a field is missing, it falls back to rendering whatever is available rather than erroring.

**Final output to user:**
<!-- What does the user actually see at the end? -->
The user sees 3 UI panels:
 (1) the listing found (lst_006: price, condition, platform);
 (2) the outfit idea (tee styled with the baggy jeans + chunky sneakers);
 (3) the fit card summary.
For a no-match query (e.g. "designer ballgown size XXS under $5"), the agent stops at Step 1 — panel 1 shows a friendly "no listings matched" message, and panels 2 and 3 stay empty.
