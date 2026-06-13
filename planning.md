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
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): ...
- `size` (str): ...
- `max_price` (float): ...

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): ...
- `wardrobe` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

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

**Milestone 4 — Planning loop and state management:**




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
