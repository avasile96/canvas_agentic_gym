"""Gymnasium environment for MarketCanvas."""

import json

import gymnasium
import numpy as np
from gymnasium import spaces

from marketcanvas.actions import (
    COLOR_PALETTE,
    TEXT_OPTIONS,
    LowLevelActionInterpreter,
    execute_high_level,
)
from marketcanvas.canvas import Canvas
from marketcanvas.prompt_parser import parse_prompt
from marketcanvas.renderer import CanvasRenderer
from marketcanvas.reward import RewardCalculator

_HL_ACTIONS = [
    "add_text", "add_shape", "add_image", "remove",
    "move", "resize", "change_color", "change_text",
]
_LL_ACTIONS = ["mouse_click", "mouse_drag", "mouse_move", "keyboard_type"]


class MarketCanvasEnv(gymnasium.Env):
    """2D canvas RL environment for design agents.

    Supports two action modes:
      - "high_level": semantic actions (add_text, move, etc.)
      - "low_level": mouse/keyboard actions (click, drag, type)
    """

    metadata = {"render_modes": ["rgb_array"]}

    def __init__(
        self,
        prompt: str = "Create a marketing banner with a headline, a CTA button, and an image",
        action_mode: str = "high_level",
        max_steps: int = 50,
        render_mode: str | None = "rgb_array",
    ):
        super().__init__()
        self.prompt = prompt
        self.action_mode = action_mode
        self.max_steps = max_steps
        self.render_mode = render_mode

        self.constraints = parse_prompt(prompt)
        self.reward_calc = RewardCalculator(self.constraints)

        # Observation: rendered image + semantic JSON
        self.observation_space = spaces.Dict({
            "visual": spaces.Box(0, 255, shape=(600, 800, 3), dtype=np.uint8),
            "semantic": spaces.Text(max_length=10_000),
        })

        # Action space
        if action_mode == "high_level":
            self.action_space = spaces.Dict({
                "action_type": spaces.Discrete(len(_HL_ACTIONS)),
                "x": spaces.Box(0, 800, shape=(), dtype=np.float32),
                "y": spaces.Box(0, 600, shape=(), dtype=np.float32),
                "width": spaces.Box(10, 800, shape=(), dtype=np.float32),
                "height": spaces.Box(10, 600, shape=(), dtype=np.float32),
                "color_idx": spaces.Discrete(len(COLOR_PALETTE)),
                "element_idx": spaces.Discrete(20),
                "text_idx": spaces.Discrete(len(TEXT_OPTIONS)),
            })
        else:
            self.action_space = spaces.Dict({
                "action_type": spaces.Discrete(len(_LL_ACTIONS)),
                "x": spaces.Box(0, 800, shape=(), dtype=np.float32),
                "y": spaces.Box(0, 600, shape=(), dtype=np.float32),
                "x2": spaces.Box(0, 800, shape=(), dtype=np.float32),
                "y2": spaces.Box(0, 600, shape=(), dtype=np.float32),
                "text_idx": spaces.Discrete(len(TEXT_OPTIONS)),
            })

        self.canvas: Canvas = Canvas()
        self.renderer: CanvasRenderer = CanvasRenderer(self.canvas)
        self.low_level: LowLevelActionInterpreter = LowLevelActionInterpreter(self.canvas)
        self._step_count: int = 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if options and "prompt" in options:
            self.prompt = options["prompt"]
            self.constraints = parse_prompt(self.prompt)
            self.reward_calc = RewardCalculator(self.constraints)

        self.canvas = Canvas()
        self.renderer = CanvasRenderer(self.canvas)
        self.low_level = LowLevelActionInterpreter(self.canvas)
        self._step_count = 0
        return self._obs(), self._info()

    def step(self, action):
        """Execute encoded numeric action (for RL)."""
        if self.action_mode == "high_level":
            self._step_hl(action)
        else:
            self._step_ll(action)

        self._step_count += 1
        reward = self.reward_calc.compute(self.canvas)
        truncated = self._step_count >= self.max_steps
        info = self._info()
        info["reward_breakdown"] = reward
        return self._obs(), reward["total"], False, truncated, info

    def execute_named_action(self, action_type: str, **params) -> dict:
        """Execute a string-based action (for MCP / demo).

        Returns dict with success, reward_breakdown, step_count, truncated.
        """
        if action_type in _HL_ACTIONS:
            ok = execute_high_level(self.canvas, action_type, **params)
        elif action_type == "mouse_click":
            ok = self.low_level.mouse_click(params.get("x", 0), params.get("y", 0))
        elif action_type == "mouse_drag":
            ok = self.low_level.mouse_drag(
                params.get("x1", 0), params.get("y1", 0),
                params.get("x2", 0), params.get("y2", 0),
            )
        elif action_type == "mouse_move":
            self.low_level.mouse_move(params.get("x", 0), params.get("y", 0))
            ok = True
        elif action_type == "keyboard_type":
            ok = self.low_level.keyboard_type(params.get("text", ""))
        else:
            ok = False

        self._step_count += 1
        reward = self.reward_calc.compute(self.canvas)
        return {
            "success": ok,
            "reward_breakdown": reward,
            "step_count": self._step_count,
            "truncated": self._step_count >= self.max_steps,
        }

    def render(self):
        if self.render_mode == "rgb_array":
            return self.renderer.render_to_array()
        return None

    # ── Private helpers ───────────────────────────────────────────

    def _obs(self) -> dict:
        return {
            "visual": self.renderer.render_to_array(),
            "semantic": json.dumps(self.canvas.to_semantic_state()),
        }

    def _info(self) -> dict:
        return {
            "step_count": self._step_count,
            "element_count": len(self.canvas.elements),
            "prompt": self.prompt,
        }

    def _step_hl(self, action: dict) -> None:
        name = _HL_ACTIONS[int(action["action_type"])]
        x, y = float(action["x"]), float(action["y"])
        w, h = float(action["width"]), float(action["height"])
        color = COLOR_PALETTE[int(action["color_idx"])]
        text = TEXT_OPTIONS[int(action["text_idx"])]
        el_idx = int(action["element_idx"])

        el_id = ""
        if el_idx < len(self.canvas.elements):
            el_id = self.canvas.elements[el_idx].id

        params: dict = {}
        if name == "add_text":
            params = dict(x=x, y=y, width=w, height=h, color=color, content=text)
        elif name == "add_shape":
            params = dict(x=x, y=y, width=w, height=h, color=color,
                          shape_kind="button", text_content=text)
        elif name == "add_image":
            params = dict(x=x, y=y, width=w, height=h, color=color, alt_text=text)
        elif name == "remove":
            params = dict(element_id=el_id)
        elif name == "move":
            params = dict(element_id=el_id, x=x, y=y)
        elif name == "resize":
            params = dict(element_id=el_id, width=w, height=h)
        elif name == "change_color":
            params = dict(element_id=el_id, color=color)
        elif name == "change_text":
            params = dict(element_id=el_id, text=text)

        execute_high_level(self.canvas, name, **params)

    def _step_ll(self, action: dict) -> None:
        name = _LL_ACTIONS[int(action["action_type"])]
        x, y = float(action["x"]), float(action["y"])

        if name == "mouse_click":
            self.low_level.mouse_click(x, y)
        elif name == "mouse_drag":
            self.low_level.mouse_drag(x, y, float(action["x2"]), float(action["y2"]))
        elif name == "mouse_move":
            self.low_level.mouse_move(x, y)
        elif name == "keyboard_type":
            self.low_level.keyboard_type(TEXT_OPTIONS[int(action["text_idx"])])
