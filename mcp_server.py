"""MCP server wrapping the MarketCanvas environment."""

import io
import json

from mcp.server.fastmcp import FastMCP, Image

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
    """Return reward breakdown: total score plus constraint, aesthetics, and accessibility sub-scores."""
    return json.dumps(_env.reward_calc.compute(_env.canvas))


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


if __name__ == "__main__":
    mcp.run()
