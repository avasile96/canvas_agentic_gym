"""Scripted demo: build a Summer Sale banner, print reward progression, save PNG."""

import json
import sys

from marketcanvas.env import MarketCanvasEnv
from marketcanvas.renderer import CanvasRenderer

PROMPT = (
    "Create a Summer Sale email banner with a bold headline, "
    "a yellow CTA button that says 'Shop Now', and a product image"
)


def print_step(label: str, result: dict) -> None:
    rb = result["reward_breakdown"]
    print(f"  [{result['step_count']:2d}] {label:<30s}  "
          f"reward={rb['total']:+.3f}  "
          f"(constr={rb['constraint_satisfaction']:.2f}  "
          f"aesth={rb['aesthetics']:.2f}  "
          f"access={rb['accessibility']:.2f})")


def build_banner() -> None:
    """Build a banner step-by-step with high-level actions."""
    print("=" * 72)
    print("MarketCanvas Demo — Scripted Banner Build")
    print("=" * 72)
    print(f"\nPrompt: {PROMPT}\n")

    env = MarketCanvasEnv(prompt=PROMPT)
    env.reset()

    # ── High-level actions ────────────────────────────────────────

    print("── High-level actions ──")

    r = env.execute_named_action("add_shape", x=0, y=0, width=800, height=600,
                                  color="#1A1A1A", shape_kind="rectangle")
    print_step("Add dark background", r)

    r = env.execute_named_action("add_text", x=150, y=40, width=500, height=60,
                                  content="Summer Sale!", text_color="#FFFFFF",
                                  color="#1A1A1A", font_size=48, bold=True)
    print_step("Add headline", r)

    r = env.execute_named_action("add_text", x=200, y=110, width=400, height=35,
                                  content="Up to 50% off everything",
                                  text_color="#CCCCCC", color="#1A1A1A", font_size=20)
    print_step("Add subtext", r)

    r = env.execute_named_action("add_image", x=250, y=170, width=300, height=200,
                                  color="#2A2A2A", alt_text="Product Image")
    print_step("Add product image", r)

    r = env.execute_named_action("add_shape", x=275, y=410, width=250, height=65,
                                  color="#FFD700", shape_kind="button",
                                  text_content="Shop Now", text_color="#000000",
                                  border_radius=12)
    print_step("Add CTA button", r)

    r = env.execute_named_action("add_text", x=250, y=510, width=300, height=25,
                                  content="Free shipping on orders over $50",
                                  text_color="#999999", color="#1A1A1A", font_size=14)
    print_step("Add footer text", r)

    # ── Low-level actions ─────────────────────────────────────────

    print("\n── Low-level actions ──")

    r = env.execute_named_action("mouse_click", x=400, y=440)
    print_step("Click CTA button", r)
    sel = env.canvas.get_selected()
    print(f"       Selected: {sel.id if sel else 'None'}"
          f" ({getattr(sel, 'text_content', '')!r})")

    r = env.execute_named_action("mouse_drag", x1=400, y1=440, x2=400, y2=420)
    print_step("Drag CTA up 20px", r)

    # ── Final state ───────────────────────────────────────────────

    print("\n── Final semantic state ──")
    state = env.canvas.to_semantic_state()
    print(json.dumps(state, indent=2))

    # ── Save PNG ──────────────────────────────────────────────────

    renderer = CanvasRenderer(env.canvas)
    renderer.save_png("output/final_banner.png")
    print(f"\nSaved output/final_banner.png")


def random_agent_contrast() -> None:
    """Run 20 random actions to show how random exploration yields low reward."""
    print("\n" + "=" * 72)
    print("Random Agent Contrast — 20 random actions")
    print("=" * 72)

    env = MarketCanvasEnv(prompt=PROMPT, action_mode="high_level", max_steps=20)
    env.reset()

    for i in range(20):
        action = env.action_space.sample()
        obs, reward, term, trunc, info = env.step(action)
        if (i + 1) % 5 == 0 or i == 0:
            print(f"  Step {i+1:2d}: reward={reward:+.3f}  "
                  f"elements={info['element_count']}")
        if trunc:
            break

    final = env.reward_calc.compute(env.canvas)
    print(f"\n  Final reward: {final['total']:+.3f}")
    print(f"  (Scripted agent gets ~+0.9, random agent gets ~{final['total']:+.3f})")

    renderer = CanvasRenderer(env.canvas)
    renderer.save_png("output/random_banner.png")
    print(f"  Saved output/random_banner.png")


if __name__ == "__main__":
    build_banner()
    if "--random" in sys.argv or "--all" in sys.argv:
        random_agent_contrast()
    print("\nDone.")
