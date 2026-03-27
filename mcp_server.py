"""MCP server wrapping the MarketCanvas environment."""

import io
import json

from mcp.server.fastmcp import FastMCP, Image

from marketcanvas.canvas import Canvas
from marketcanvas.elements import ImageElement, ShapeElement, ShapeKind, TextElement
from marketcanvas.env import MarketCanvasEnv

mcp = FastMCP("MarketCanvas")

# Shared environment instance
_env = MarketCanvasEnv()
_env.reset()


@mcp.tool()
def reset_environment(prompt: str) -> str:
    """Reset the canvas with a new design prompt. Returns initial state and parsed constraints."""
    _env.reset(options={"prompt": prompt})
    return json.dumps({
        "state": _env.canvas.to_semantic_state(),
        "constraints": {
            "required_elements": [
                {"type": r.element_type, "keywords": r.keywords, "color_hint": r.color_hint}
                for r in _env.constraints.required_elements
            ],
            "color_hints": _env.constraints.color_hints,
            "content_keywords": _env.constraints.content_keywords,
        },
    })


@mcp.tool()
def get_canvas_state() -> str:
    """Return the current semantic DOM tree of the canvas as JSON."""
    return json.dumps(_env.canvas.to_semantic_state())


@mcp.tool()
def execute_action(action_type: str, **params) -> str:
    """Execute a high-level or low-level action on the canvas.

    High-level: add_text, add_shape, add_image, remove, move, resize, change_color, change_text
    Low-level: mouse_click, mouse_drag, mouse_move, keyboard_type

    Returns success status, new state, and reward breakdown.
    """
    result = _env.execute_named_action(action_type, **params)
    result["state"] = _env.canvas.to_semantic_state()
    return json.dumps(result, default=str)


@mcp.tool()
def get_current_reward() -> str:
    """Return reward breakdown with per-element diagnostics for actionable LLM feedback.

    Includes total score, three sub-scores, and a diagnostics list with messages like
    'contrast ratio 2.8 — below AA' or 'element not horizontally centered (+45px)'.
    """
    return json.dumps(_env.reward_calc.compute_with_diagnostics(_env.canvas))


@mcp.tool()
def render_canvas() -> Image:
    """Render the current canvas as a PNG image."""
    img = _env.renderer.render()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Image(data=buf.getvalue(), format="png")


@mcp.resource("canvas://state")
def canvas_state_resource() -> str:
    """Live canvas state as JSON."""
    return json.dumps(_env.canvas.to_semantic_state())


def _state_dict_to_canvas(state: dict) -> Canvas:
    """Reconstruct a Canvas from a to_semantic_state() dict."""
    c = state.get("canvas", {})
    canvas = Canvas(
        width=c.get("width", 800),
        height=c.get("height", 600),
        background_color=c.get("background_color", "#FFFFFF"),
    )
    for entry in state.get("elements", []):
        etype = entry.get("type")
        common = dict(
            id=entry["id"],
            x=entry["x"], y=entry["y"],
            width=entry["width"], height=entry["height"],
            z_index=entry["z_index"],
            color=entry["color"],
        )
        if etype == "text":
            canvas.add_element(TextElement(
                **common,
                content=entry.get("content", ""),
                text_color=entry.get("text_color", "#000000"),
                font_size=entry.get("font_size", 16),
                bold=entry.get("bold", False),
            ))
        elif etype == "shape":
            canvas.add_element(ShapeElement(
                **common,
                shape_kind=ShapeKind(entry.get("shape_kind", "rectangle")),
                text_content=entry.get("text_content", ""),
                text_color=entry.get("text_color", "#000000"),
                border_radius=entry.get("border_radius", 0),
            ))
        elif etype == "image":
            canvas.add_element(ImageElement(
                **common,
                alt_text=entry.get("alt_text", ""),
            ))
    return canvas


@mcp.tool()
def compare_canvas_states(state_a: str, state_b: str) -> str:
    """Compare two canvas semantic states and return which scores higher.

    Pass JSON strings from get_canvas_state() on two different canvas configurations.
    Returns the winner ('a' or 'b'), per-pillar scores for each, and the deltas.
    Pairwise comparison is more reliable than absolute scoring for design evaluation.
    """
    dict_a = json.loads(state_a)
    dict_b = json.loads(state_b)
    canvas_a = _state_dict_to_canvas(dict_a)
    canvas_b = _state_dict_to_canvas(dict_b)
    reward_a = _env.reward_calc.compute(canvas_a)
    reward_b = _env.reward_calc.compute(canvas_b)
    winner = "a" if reward_a["total"] >= reward_b["total"] else "b"
    return json.dumps({
        "winner": winner,
        "state_a": reward_a,
        "state_b": reward_b,
        "delta": {k: round(reward_a[k] - reward_b[k], 4) for k in reward_a},
    })


if __name__ == "__main__":
    mcp.run()
