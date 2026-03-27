# MarketCanvas-Env Implementation Plan

## Context

Verita AI builds LLM agents that autonomously operate design software (Canva, Figma) via direct computer use, trained with RL. This take-home assignment asks us to build **MarketCanvas-Env**: a minimalist 2D canvas that exposes a standard RL interface (State, Action, Reward) and simultaneously acts as an MCP server for LLM tool-calling. No model training required -- focus is on environment design, MDP formulation, and API tooling.

## Project Structure

```
assignment_2/
├── marketcanvas/
│   ├── __init__.py
│   ├── elements.py        # Pydantic models: TextElement, ShapeElement, ImageElement
│   ├── canvas.py           # Core 2D canvas engine (CRUD, hit-testing, serialization)
│   ├── renderer.py         # PIL-based rendering to PNG / numpy array
│   ├── wcag.py             # WCAG 2.1 contrast ratio utilities
│   ├── prompt_parser.py    # Parse target prompts into PromptConstraints
│   ├── reward.py           # Heuristic reward: constraints + aesthetics + accessibility
│   ├── actions.py          # Action definitions + LowLevelActionInterpreter
│   └── env.py              # Gymnasium environment (MarketCanvasEnv)
├── mcp_server.py           # MCP server wrapping the environment
├── demo.py                 # Scripted demo: build a banner, print state + reward, save PNG
├── tests/
│   ├── test_canvas.py
│   ├── test_reward.py
│   ├── test_wcag.py
│   └── test_env.py
├── WRITEUP.md
├── README.md
├── requirements.txt
└── pyproject.toml
```

## Implementation Phases

### Phase 1: Data Models + Core Engine
**Files:** `elements.py`, `canvas.py`, `wcag.py`

- **`elements.py`** -- Pydantic models with base `CanvasElement` (id, x, y, width, height, z_index, color, content) and subclasses `TextElement` (text_color, font_size, bold), `ShapeElement` (shape_kind: rectangle/button, border_radius, text_content, text_color), `ImageElement` (alt_text). Include `bbox()`, `center()`, `overlaps()`, `overlap_area()` helpers.

- **`canvas.py`** -- `Canvas` class (800x600, configurable background_color):
  - CRUD: `add_element()`, `remove_element()`, `move_element()`, `resize_element()`, `change_color()`, `change_text()`
  - Low-level support: `hit_test(x, y)` returns topmost element by z-index, `select()`/`get_selected()`
  - Serialization: `to_semantic_state()` returns JSON DOM with element properties + spatial metadata (center, horizontally_centered, overlaps_with, nearest_neighbors)
  - Cap at 20 elements max

- **`wcag.py`** -- `relative_luminance(r, g, b)`, `contrast_ratio(hex1, hex2)`, `meets_aa()` per WCAG 2.1 spec

**QA gate:** Run `pytest tests/test_canvas.py tests/test_wcag.py`. Review all files for unnecessary abstractions — each function should do one thing, no speculative helpers. Prefer flat logic over deeply nested classes. If a method exceeds ~30 lines, reconsider the approach before splitting into helpers.

### Phase 2: Rendering
**File:** `renderer.py`

- `CanvasRenderer` takes a `Canvas`, produces PIL `Image`
- Draws elements in z-order: filled rectangles, text via ImageDraw, image placeholders as colored boxes with diagonal cross + label
- Selected element gets blue dashed border
- Methods: `render() -> Image`, `render_to_array() -> ndarray(600,800,3)`, `save_png(path)`
- Fallback font handling (truetype with fallback to default)

**QA gate:** Render a canvas with one of each element type, save PNG, visually inspect. Run `pytest tests/test_canvas.py` to confirm rendering doesn't break canvas state. Check that `renderer.py` is a single class with no unnecessary indirection — PIL drawing is inherently procedural, don't over-abstract it.

### Phase 3: Reward System
**Files:** `prompt_parser.py`, `reward.py`

- **`prompt_parser.py`** -- `parse_prompt(text) -> PromptConstraints` using keyword/regex matching. Extracts: required elements (headline->Text, CTA/button->Shape, image->Image), color hints (color words -> hex palette), content keywords, layout preferences.

- **`reward.py`** -- `RewardCalculator(constraints)` computes scalar in [-1.0, 1.0]:
  - **Constraint satisfaction (50%)**: For each required element, check type match + content keywords + color hint. Score per element: 1.0 (full match), 0.5 (type only), 0.0 (absent). Average across requirements.
  - **Aesthetics (25%)**: overlap penalty (30%), horizontal alignment to center (30%), bounds check (20%), vertical spacing consistency (20%).
  - **Accessibility (25%)**: WCAG contrast ratio for each text element against its effective background (closest element underneath by z-index, or canvas bg). Score: 1.0 if ratio >= 4.5 (AA), 0.5 if >= 3.0, 0.0 otherwise. Average across text elements.
  - Final: `reward = 2 * weighted_sum - 1` mapping [0,1] to [-1,1]

**QA gate:** Run `pytest tests/test_reward.py`. Verify edge cases: empty canvas → minimum reward, perfect layout → near-maximum reward, single overlapping element → penalty. Check that `prompt_parser.py` uses simple keyword matching — no NLP libraries, no over-engineered regex. The reward calculator should be one class with clear arithmetic, not a tree of strategy objects.

### Phase 4: Actions + Gymnasium Environment
**Files:** `actions.py`, `env.py`

- **`actions.py`** -- `LowLevelActionInterpreter` maintains mouse state, translates:
  - `mouse_click()` -> hit-test + select
  - `mouse_drag(x1,y1,x2,y2)` -> select at start + move by delta
  - `keyboard_type(text)` -> update selected element's content
  - `mouse_move(x,y)` -> update cursor position

- **`env.py`** -- `MarketCanvasEnv(gymnasium.Env)`:
  - `action_mode` param: "high_level" or "low_level"
  - Observation space: Dict with `visual` (Box 600x800x3) + `semantic` (Text)
  - High-level action space: Dict of Discrete/Box (action_type, element_type, x, y, width, height, color_idx into 16-color palette, element_idx, text_idx into 10 predefined texts)
  - Low-level action space: Dict of Discrete/Box (action_type, x, y, x2, y2, text_idx)
  - `step()` for encoded numeric actions (RL), `execute_named_action()` for string-based actions (MCP/demo)
  - Dense reward at every step; episode ends at `max_steps` (default 50)

**QA gate:** Run `pytest tests/test_env.py`. Test full `reset()` → `step()` × N cycle in both action modes. Verify `execute_named_action()` and numeric `step()` produce identical canvas states for the same logical action. Check for code bloat: `actions.py` should be thin translation logic, not a framework. `env.py` should delegate to canvas + reward, not reimplement their logic.

### Phase 5: MCP Server
**File:** `mcp_server.py`

Using `mcp[cli]` SDK with `FastMCP`. Five tools:
1. **`reset_environment(prompt)`** -- Reset canvas, set new target prompt, return initial state + parsed constraints
2. **`get_canvas_state()`** -- Return semantic DOM tree JSON
3. **`execute_action(action_type, ...params)`** -- Execute high-level or low-level action, return success + new state + reward
4. **`get_current_reward()`** -- Return reward breakdown (total + 3 sub-scores)
5. **`render_canvas()`** -- Return base64-encoded PNG as ImageContent

Plus resource `canvas://state` for live state.

**QA gate:** Start the MCP server, manually call each tool via `mcp dev` or a test script, verify JSON responses are well-formed. The server should be a thin wrapper — each tool body should be ~5-10 lines delegating to the env. If any tool function exceeds 15 lines, it's doing too much.

### Phase 6: Demo + Tests
**File:** `demo.py`

Scripted demo that:
1. Initializes env with prompt: "Create a Summer Sale email banner with a bold headline, a yellow CTA button that says 'Shop Now', and a product image"
2. Executes ~6 high-level actions building a banner (dark bg, headline, subtext, image placeholder, CTA button)
3. Prints reward progression and breakdown at each step
4. Demos low-level actions (click to select CTA, drag to reposition)
5. Prints final semantic state JSON
6. Saves PNG to `output/final_banner.png`
7. Optionally: random agent contrast (20 random actions, show low reward)

**Tests:** Cover canvas CRUD, WCAG calculations, reward scoring edge cases, env reset/step.

**QA gate:** Run full `pytest tests/` — all tests green. Run `python demo.py` end-to-end, verify PNG output looks reasonable. Do a final code review pass across all files: remove any dead code, unused imports, unnecessary comments, or speculative abstractions added "just in case." The entire `marketcanvas/` package should feel like something one person wrote in a weekend, not an enterprise framework.

### Phase 6.5: Research-Informed Enhancements (post-core, in priority order)
Informed by DesignSense (arXiv 2602.23438), Design-o-meter (WACV 2025), and RL-VLM-F (ICML 2024). Only attempt after Phases 1-6 are working end-to-end.

1. **Visual hierarchy scoring** (~30 min) — Add to reward aesthetics sub-score. Check that headline has the largest area/font, CTA is visually distinct (contrasting color, sufficient size), and no secondary element dominates the primary one. Simple heuristic: rank elements by expected prominence from the prompt, penalize if visual size order doesn't match.

2. **Granular reward diagnostics via MCP** (~30 min) — Enrich `get_current_reward()` response to include per-element diagnostics: "headline overlaps CTA by 15px", "contrast ratio 2.8 — below AA", "CTA not horizontally centered." Gives an LLM agent actionable feedback, not just a scalar.

3. **Perturbation-based reward validation** (~1 hr) — Add `tests/test_perturbation.py`. Take a known-good banner layout, apply controlled degradations (random position offsets 20-50%, scale changes 0.8x-1.2x on random elements — mirroring DesignSense's augmentation strategy), verify reward drops monotonically with degradation severity. Also works as a compelling demo mode: "good layout vs. perturbed layout."

4. **Semantic grouping in observation** (~30 min) — Add a `groups` field to the semantic state JSON. Group related elements (e.g., headline + subtext = "header", CTA button + CTA text = "call-to-action") based on spatial proximity and type. Gives LLM agents richer structural context beyond a flat element list.

5. **Pairwise comparison MCP tool** (~30 min) — Add `compare_canvas_states(state_a, state_b)` tool. Returns which state scores higher with per-pillar breakdown. Research shows pairwise preference is more reliable than absolute scoring (81% vs 56% human agreement in DesignSense). Useful for LLM agents doing beam search over design options.

### Phase 7: Documentation
**File:** `WRITEUP.md` (1-2 pages)

Sections:
1. **State space rationale** -- Why both semantic JSON DOM + visual RGB. DOM for token-efficient LLM reasoning, RGB for future multimodal VLM training.
2. **Action space rationale** -- Why both levels. High-level = efficient for semantic agents (MCP/tool-calling). Low-level = needed for computer-use training (Verita's core mission). Trade-offs: high-level is easier to learn but less general; low-level matches real UI but has huge action space.
3. **Reward function design** -- Three-pillar scoring, weights, formulas. Reward hacking vulnerabilities: invisible tiny elements, white-on-black everywhere, single centered element gaming aesthetics. Mitigations: minimum dimensions, content requirements, multi-metric composition.
4. **Beyond heuristics: learned reward models (writeup discussion only, not implemented)** -- Our heuristic reward is a practical starting point; discuss the frontier as a future direction. Reference DesignSense (arXiv 2602.23438, Feb 2026): 10K human-annotated layout preference pairs, fine-tuned InternVL3-8B as reward model, 54.6% Macro F1 improvement over frontier VLMs. Key insight: generic vision models (GPT-5, o3, Gemini 2.5 Pro) cannot judge layout quality — spatial arrangement needs design-specific training data. RL-VLM-F (ICML 2024) offers a middle ground: query a VLM for pairwise preferences over canvas states, learn a reward function from those labels without human annotation. Spectrum: heuristics (fast, gameable) → VLM-as-judge (medium effort, noisy) → learned reward model on human preferences (best alignment, highest effort). Design-o-meter (WACV 2025) shows the same qualities our heuristics target (overlap, alignment, spacing, hierarchy) can be learned from data with better generalization.
5. **Scaling to 10K parallel rollouts with VLM** -- Bottlenecks: PIL rendering per step, VLM inference cost, memory for 10K canvas states. Solutions: vectorized env (gymnasium vector API), GPU-accelerated rendering (replace PIL with headless OpenGL or warp), async VLM batching, state checkpointing for rollback, sharded workers across nodes.

## Dependencies

```
gymnasium>=1.0.0
Pillow>=10.0.0
numpy>=1.24.0
pydantic>=2.0.0
mcp[cli]>=1.2.0
pytest>=7.0  # dev
```

## Verification

1. `python demo.py` -- should print reward progression, final state, and save PNG
2. `pytest tests/` -- unit tests pass
3. MCP server: `python mcp_server.py` or configure in Claude Desktop config, then use tools interactively
4. Visual check: open `output/final_banner.png` -- should show a reasonable marketing banner layout
5. Gymnasium compatibility: `gymnasium.make()` registration or direct instantiation, verify `reset()`/`step()` cycle works with random actions
