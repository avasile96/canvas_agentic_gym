# MarketCanvas-Env: Technical Writeup

## 1. State Space

MarketCanvas-Env provides a **dual observation** — a semantic JSON DOM and a visual RGB array — delivered simultaneously through a Gymnasium `Dict` space.

**Semantic state** (`Text`, up to 10K chars) is a JSON document produced by `Canvas.to_semantic_state()`. It contains every element's properties (position, size, color, content, z-index) plus computed spatial metadata: `center` coordinates, `horizontally_centered` (True if within 10px of canvas midpoint — ~1.25% tolerance, visually indistinguishable from true center but achievable by an RL agent), `overlaps_with` (IDs of overlapping elements), and `nearest_neighbors` (top 3 by Euclidean center-distance). This is analogous to a browser accessibility tree: an LLM can reason about element relationships without parsing pixels.

**Visual state** (`Box(0, 255, shape=(600, 800, 3), dtype=uint8)`) is a PIL-rendered RGB array. It captures visual properties — font rendering, color blending, spatial composition — that the semantic JSON cannot represent. This matters for Verita's mission: a multimodal agent operating real design tools via computer use needs pixel-level input to generalize beyond our simplified canvas.

**Why both?** Semantic-only is sufficient for tool-calling LLMs (MCP agents). Visual-only is necessary for VLM-based policies and computer-use training. Providing both lets the environment serve either paradigm. The semantic state is recomputed on every call (never stale), keeping the two representations synchronized.

## 2. Action Space

The environment supports two action modes, selectable at init.

**High-level** (8 actions: `add_text`, `add_shape`, `add_image`, `remove`, `move`, `resize`, `change_color`, `change_text`) maps directly to MCP tool-calling. An LLM agent executing `add_shape(x=275, y=410, color="#FFD700", text_content="Shop Now")` expresses its semantic intent in one call. The action space uses a `Dict` of `Discrete` and `Box` spaces: action type (Discrete(8)), position/size (Box), a 16-color palette index (Discrete(16)), an element index for targeting (Discrete(20)), and a 10-string text index (Discrete(10)). The palette and text discretization is a necessary RL simplification — continuous text generation would require a language model head, which is out of scope.

**Low-level** (4 actions: `mouse_click`, `mouse_drag`, `mouse_move`, `keyboard_type`) mirrors real computer-use interaction. Click performs hit-testing and selection. Drag selects at the start point and moves the element by the pixel delta. Keyboard type updates the selected element's content. This matches how a human (or a computer-use agent) would operate Canva or Figma.

**Trade-offs:** High-level actions are easier to learn — each has an immediate semantic effect, and the action space has only 8 types. But they're locked to the operations our API exposes; a real design tool has hundreds of UI interactions. Low-level actions are general — any operation achievable through a mouse and keyboard is reachable — but the continuous coordinate space is enormous, and simple operations (e.g., recoloring a button) require multi-step sequences (click to select, then invoke change). This duality is deliberate: high-level for rapid MCP prototyping, low-level for training policies that transfer to real interfaces.

Both modes share the same underlying canvas operations via delegation: `env.step()` decodes numeric actions for RL, `env.execute_named_action()` accepts strings for MCP and demos. The two paths produce identical canvas states for the same logical action.

## 3. Reward Function Design

The reward is a heuristic scalar in [-1.0, 1.0], computed statelessly from a canvas snapshot. Calling it every step provides dense gradient signal without additional cost.

**Formula:** `reward = 2 × (0.50·C + 0.25·A + 0.25·X) − 1`, where C, A, X ∈ [0, 1].

**Constraint satisfaction C (50%)** checks whether required elements are present. A prompt parser extracts requirements via keyword matching (e.g., "bold headline" → TextElement, "yellow CTA button" → ShapeElement with color hint). For each requirement, the best-matching canvas element is scored: 1.0 if type, keywords, and color all match; 0.75 for partial match; 0.5 for type-only. C is the average across requirements. Weight rationale: meeting the brief is twice as important as looking good or being readable — this prevents agents that produce aesthetically pleasing but off-prompt designs.

**Aesthetics A (25%)** combines four sub-metrics:
- *Overlap penalty (30%)*: fraction of non-overlapping element pairs. Penalizes layouts where elements stack incoherently.
- *Horizontal alignment (30%)*: average per-element distance from canvas center, normalized. Rewards centered, professional layouts.
- *Bounds check (20%)*: fraction of elements fully within the 800×600 canvas. Penalizes elements that overflow.
- *Vertical spacing consistency (20%)*: deviation of inter-element vertical gaps from their mean. Rewards evenly spaced layouts.

**Accessibility X (25%)** evaluates WCAG 2.1 contrast ratios. For each text-bearing element (TextElement or ShapeElement with text), the text color is checked against the element's fill color. Score per element: 1.0 if ratio ≥ 4.5:1 (AA), 0.5 if ≥ 3.0:1 (A), 0.0 otherwise.

**Reward hacking vulnerabilities:**
1. *Invisible elements*: A 1×1 TextElement with "Sale!" satisfies a "headline" constraint without visible contribution. Mitigation: multi-metric composition — the element won't improve aesthetics or accessibility scores.
2. *Monochrome abuse*: White text on black everywhere achieves 21:1 contrast. Mitigation: constraint satisfaction requires matching prompted colors (e.g., "yellow button"), not just high contrast.
3. *Single-element gaming*: One centered element scores perfect alignment, spacing, and bounds. Mitigation: constraint satisfaction requires multiple elements when the prompt specifies them; a single element can satisfy at most one requirement.

## 4. Beyond Heuristics: Learned Reward Models

Our heuristic reward encodes known design principles — but it's gameable and cannot capture subjective design quality. The frontier is learned reward models.

**DesignSense** (arXiv 2602.23438, Feb 2026) collected 10K human-annotated layout preference pairs and fine-tuned InternVL3-8B as a design reward model, achieving 54.6% Macro F1 improvement over frontier VLMs. The key insight: generic vision models (GPT-5, o3, Gemini 2.5 Pro) achieve ~72% binary accuracy on "is this layout good?" but fail at fine-grained preference ranking. Spatial arrangement quality requires design-specific training data — it cannot be prompt-engineered into a general-purpose VLM.

**RL-VLM-F** (ICML 2024) offers a middle ground: query a VLM for pairwise preferences over environment states, then train a reward function from those labels. No human annotation required, but quality depends on the VLM's design judgment — which DesignSense shows is limited for generic models.

**Design-o-meter** (WACV 2025) provides the first unified framework that both scores and refines graphic designs. It validates that the same qualities our heuristics target — overlap, alignment, spacing, visual hierarchy — can be learned from data with better generalization.

**The spectrum:** heuristics (fast, interpretable, gameable) → VLM-as-judge (medium effort, noisy but scalable) → learned reward model on human preference data (best alignment with human judgment, highest data/compute effort). MarketCanvas-Env's modular `RewardCalculator` is designed to be swappable — replacing `compute()` with a learned model requires no changes to the environment, action space, or MCP interface.

## 5. Scaling to 10,000 Parallel Rollouts with VLM

Running PPO with 10K parallel environments and a VLM-based reward introduces three bottleneck categories.

**Rendering.** PIL is CPU-bound at ~5ms per frame. At 10K environments × 50 steps per episode, that's 500K renders per batch — ~40 minutes on a single core. Solutions: (1) GPU-accelerated rendering via headless OpenGL (ModernGL), NVIDIA Warp, or batched tensor operations that render all 10K canvases in a single kernel; (2) render-on-demand — only render when the VLM reward model needs a visual observation, not every step.

**VLM inference.** If using visual observations or VLM-as-judge reward, inference dominates wall time. Solutions: (1) async batching — collect observation images from N environments and batch into a single VLM forward pass, decoupling environment stepping from reward computation; (2) reward model distillation — train a lightweight CNN to approximate the VLM's preferences, reducing per-step inference from seconds to milliseconds.

**Memory.** 10K canvas states with 600×800×3 uint8 observations = ~14GB just for the visual buffer. Solutions: (1) Gymnasium's `AsyncVectorEnv` with shared memory observation buffers across worker processes; (2) state checkpointing — serialize the lightweight `Canvas` object (~20 Pydantic models) for rollback during tree search without storing pixel arrays; (3) semantic-only observations for environments where the policy doesn't need pixels, reducing per-env memory from ~1.4MB to ~1KB.

**Architecture.** Distribute 10K environments across multiple nodes using standard distributed RL patterns (IMPALA, SEED RL). Each node runs a shard of environments, renders locally, and sends trajectories to a central learner. The heuristic reward is O(n²) in elements per canvas but negligible versus rendering cost. A learned reward model adds inference cost per step — batch reward queries across parallel environments to amortize GPU utilization.
