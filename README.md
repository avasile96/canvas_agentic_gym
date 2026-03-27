# MarketCanvas-Env

A minimal, deterministic 2D design canvas that works as both a **Gymnasium RL environment** and an **MCP server** for LLM tool-calling.

Built as a take-home assignment for an ML Engineer (RL/Agents) role.

---

## What It Does

The environment simulates a simplified design canvas (think Canva, 800×600px). An agent — RL policy or LLM — places and manipulates elements (text, shapes, images) to satisfy a design prompt. At each step, the environment returns an observation, a scalar reward, and a done flag.

The MCP server wraps that same environment in five tools so an LLM can interact with it through structured function calls.

---

## Setup

```bash
pip install -e .
```

Requires Python ≥ 3.11.

**Run the demo:**

```bash
python demo.py
# with random baseline:
python demo.py --all
```

**Start the MCP server:**

```bash
python mcp_server.py
```

---

## Project Structure

```
marketcanvas/
├── elements.py       # Pydantic data models (TextElement, ShapeElement, ImageElement)
├── canvas.py         # Canvas engine: CRUD, hit-testing, serialization
├── renderer.py       # PIL-based rendering → PNG / numpy array
├── wcag.py           # WCAG 2.1 contrast ratio calculations
├── prompt_parser.py  # Prompt → structured constraints (regex only, no NLP)
├── reward.py         # Heuristic reward function
├── actions.py        # High-level and low-level action interpreters
└── env.py            # Gymnasium environment

mcp_server.py         # FastMCP server (5 tools)
demo.py               # Scripted banner build + random agent baseline
tests/                # pytest suite
```

---

## MDP Formulation

| | |
|---|---|
| **Canvas** | 800×600px, up to 20 elements, configurable background |
| **Elements** | `TextElement`, `ShapeElement` (rectangle/button), `ImageElement` |
| **Observation** | Semantic JSON DOM + RGB pixel array (600×800×3) |
| **Action space** | High-level (8 named operations) or low-level (mouse/keyboard) |
| **Reward** | Scalar in [−1, 1], dense, computed every step |
| **Termination** | Truncated at `max_steps` (default 50); no natural terminal state |

### Observation

Two parallel representations, always in sync:

- **Semantic DOM** — a JSON accessibility tree with element positions, overlaps, neighbors, and centering flags. Designed for token-efficient LLM consumption.
- **Visual array** — raw RGB pixels. Useful for multimodal/VLM policies and computer-use training.

### Action Space

Two modes, selectable at init:

**High-level** (`action_mode="high_level"`) — `Discrete(8)` type index + continuous coordinates + discrete color/text/element indices. Intended for rapid prototyping with LLMs or simple RL agents.

**Low-level** (`action_mode="low_level"`) — `Discrete(4)` type index covering `mouse_move`, `mouse_click`, `mouse_drag`, `keyboard_type`. Intended for policies that should transfer to real UI interfaces.

Both modes route through the same canvas operations and produce identical state.

### Reward Function

Three-pillar weighted sum:

```
reward = 2 × (0.50·C + 0.25·A + 0.25·X) − 1
```

| Pillar | Weight | What It Measures |
|---|---|---|
| **C** — Constraint satisfaction | 50% | Required element types, content keywords, and color hints from the prompt |
| **A** — Aesthetics | 25% | Non-overlapping layout, horizontal alignment, boundary containment, vertical spacing consistency |
| **X** — Accessibility | 25% | WCAG 2.1 contrast ratio (AA standard: ≥ 4.5:1 normal text, ≥ 3:1 large text) |

The three-pillar structure prevents single-metric gaming. A 1×1 invisible element can satisfy a constraint but tanks aesthetics. Monochrome abuse is blocked by color-hint matching. Adding a single element of the right type only gets you to 0.5C; the other two pillars still need to be addressed.

---

## Design Decisions

**Semantic + visual observations together.** The semantic DOM costs almost nothing to generate and is what an LLM actually needs. The visual array is there for multimodal policies and is pre-formatted as a Gym `Box` space. Keeping both always available avoids brittle mode-switching logic.

**Dual action space, single canvas backend.** High-level actions are easier to use in demos and LLM prompting. Low-level mouse/keyboard actions are more realistic for training policies that generalize. Both delegate to the same canvas methods, so the behavior is guaranteed to be identical — there's no divergence between "easy mode" and "hard mode."

**No NLP in prompt parsing.** `prompt_parser.py` uses only keyword matching and regex. This keeps the dependency footprint small and the behavior deterministic. There's no model to version, warm up, or fail silently.

**Stateless reward.** `RewardCalculator.compute(canvas)` is a pure function of canvas state. It's called every step with no accumulation or memory. This gives dense gradient signal and makes reward debugging straightforward — you can call it on any canvas snapshot at any time.

**Pydantic models, mutable operations.** Elements are defined with Pydantic v2 for validated construction. Canvas operations mutate element attributes directly afterward. This is a deliberate simplification: strict immutability would add boilerplate without benefit at this scale.

**Thin MCP server.** Each tool in `mcp_server.py` is 5–10 lines. It delegates to the environment; it does not reimplement logic. The environment is the source of truth.

---

## Scaling Notes

At 10K parallel rollouts, PIL rendering becomes the bottleneck (~5ms/frame → ~500K renders/batch). Practical mitigations:

- **Semantic-only observations** reduce memory from ~1.4 MB to ~1 KB per environment and skip rendering entirely for policy rollouts that don't need pixels.
- **Render-on-demand** — only render when the VLM/policy actually needs a visual observation.
- **GPU-accelerated rendering** via ModernGL or NVIDIA Warp for visual-heavy workloads.
- **`AsyncVectorEnv` with shared-memory observation buffers** for multi-process rollout without unnecessary copies.

---

## Tests

```bash
pytest
```

Covers canvas CRUD, reward calculations, WCAG contrast logic, and environment step/reset behavior.
