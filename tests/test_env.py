"""Tests for MarketCanvasEnv gymnasium environment."""

import json

import numpy as np
import pytest

from marketcanvas.actions import COLOR_PALETTE, TEXT_OPTIONS
from marketcanvas.env import MarketCanvasEnv


PROMPT = "Create a banner with a headline, a CTA button, and an image"


# ── Reset ─────────────────────────────────────────────────────────


class TestReset:
    def test_returns_obs_and_info(self):
        env = MarketCanvasEnv(prompt=PROMPT)
        obs, info = env.reset()
        assert "visual" in obs
        assert "semantic" in obs
        assert info["step_count"] == 0
        assert info["element_count"] == 0

    def test_obs_shapes(self):
        env = MarketCanvasEnv(prompt=PROMPT)
        obs, _ = env.reset()
        assert obs["visual"].shape == (600, 800, 3)
        assert obs["visual"].dtype == np.uint8
        assert isinstance(obs["semantic"], str)
        state = json.loads(obs["semantic"])
        assert state["canvas"]["width"] == 800

    def test_reset_clears_canvas(self):
        env = MarketCanvasEnv(prompt=PROMPT)
        env.reset()
        env.execute_named_action("add_text", x=100, y=50, content="Hi")
        assert len(env.canvas.elements) == 1
        env.reset()
        assert len(env.canvas.elements) == 0

    def test_reset_with_new_prompt(self):
        env = MarketCanvasEnv(prompt=PROMPT)
        env.reset()
        env.reset(options={"prompt": "Just a title"})
        assert env.prompt == "Just a title"


# ── High-level step ───────────────────────────────────────────────


class TestHighLevelStep:
    def test_add_text_step(self):
        env = MarketCanvasEnv(prompt=PROMPT, action_mode="high_level")
        env.reset()
        action = {
            "action_type": 0,  # add_text
            "x": np.float32(100),
            "y": np.float32(50),
            "width": np.float32(200),
            "height": np.float32(50),
            "color_idx": 0,
            "element_idx": 0,
            "text_idx": 0,  # "Sale!"
        }
        obs, reward, term, trunc, info = env.step(action)
        assert len(env.canvas.elements) == 1
        assert isinstance(reward, float)
        assert term is False

    def test_step_increments_count(self):
        env = MarketCanvasEnv(prompt=PROMPT, action_mode="high_level")
        env.reset()
        action = env.action_space.sample()
        env.step(action)
        assert env._step_count == 1
        env.step(action)
        assert env._step_count == 2

    def test_truncation_at_max_steps(self):
        env = MarketCanvasEnv(prompt=PROMPT, action_mode="high_level", max_steps=3)
        env.reset()
        action = env.action_space.sample()
        for i in range(2):
            _, _, _, trunc, _ = env.step(action)
            assert trunc is False
        _, _, _, trunc, _ = env.step(action)
        assert trunc is True

    def test_multi_step_reward_progression(self):
        env = MarketCanvasEnv(prompt=PROMPT, action_mode="high_level")
        env.reset()
        # Add a text element (matches headline constraint)
        r1 = env.execute_named_action("add_text", x=300, y=50, width=200, height=50,
                                       content="Summer Sale")
        # Add a shape (matches button constraint)
        r2 = env.execute_named_action("add_shape", x=300, y=400, width=200, height=60,
                                       color="#FFD700", text_content="Shop Now",
                                       shape_kind="button")
        # Reward should improve as constraints are met
        assert r2["reward_breakdown"]["total"] >= r1["reward_breakdown"]["total"]


# ── Low-level step ────────────────────────────────────────────────


class TestLowLevelStep:
    def test_click_step(self):
        env = MarketCanvasEnv(prompt=PROMPT, action_mode="low_level")
        env.reset()
        action = {
            "action_type": 0,  # mouse_click
            "x": np.float32(400),
            "y": np.float32(300),
            "x2": np.float32(0),
            "y2": np.float32(0),
            "text_idx": 0,
        }
        obs, reward, term, trunc, info = env.step(action)
        assert isinstance(reward, float)

    def test_drag_moves_element(self):
        env = MarketCanvasEnv(prompt=PROMPT, action_mode="low_level")
        env.reset()
        # First add an element via named action
        env.execute_named_action("add_text", x=100, y=100, width=200, height=50,
                                  content="Drag me")
        el = env.canvas.elements[0]
        orig_x = el.x
        # Drag it
        action = {
            "action_type": 1,  # mouse_drag
            "x": np.float32(200),    # start inside element
            "y": np.float32(125),
            "x2": np.float32(300),   # drag 100px right
            "y2": np.float32(125),
            "text_idx": 0,
        }
        env.step(action)
        assert el.x == orig_x + 100

    def test_keyboard_type(self):
        env = MarketCanvasEnv(prompt=PROMPT, action_mode="low_level")
        env.reset()
        env.execute_named_action("add_text", x=100, y=100, width=200, height=50,
                                  content="Old text")
        # Click to select
        env.execute_named_action("mouse_click", x=200, y=125)
        assert env.canvas.get_selected() is not None
        # Type new text
        action = {
            "action_type": 3,  # keyboard_type
            "x": np.float32(0),
            "y": np.float32(0),
            "x2": np.float32(0),
            "y2": np.float32(0),
            "text_idx": 1,  # "Shop Now"
        }
        env.step(action)
        assert env.canvas.elements[0].content == "Shop Now"


# ── execute_named_action ──────────────────────────────────────────


class TestNamedAction:
    def test_add_text(self):
        env = MarketCanvasEnv(prompt=PROMPT)
        env.reset()
        result = env.execute_named_action("add_text", x=100, y=50,
                                           width=200, height=50, content="Hello")
        assert result["success"] is True
        assert result["step_count"] == 1
        assert len(env.canvas.elements) == 1

    def test_unknown_action(self):
        env = MarketCanvasEnv(prompt=PROMPT)
        env.reset()
        result = env.execute_named_action("fly_to_moon")
        assert result["success"] is False

    def test_returns_reward_breakdown(self):
        env = MarketCanvasEnv(prompt=PROMPT)
        env.reset()
        result = env.execute_named_action("add_text", x=350, y=100, content="Hi")
        rb = result["reward_breakdown"]
        assert "total" in rb
        assert "constraint_satisfaction" in rb
        assert "aesthetics" in rb
        assert "accessibility" in rb


# ── Numeric vs named action equivalence ───────────────────────────


class TestActionEquivalence:
    def test_add_text_same_result(self):
        """Both paths should produce the same canvas element."""
        text = TEXT_OPTIONS[0]  # "Sale!"
        color = COLOR_PALETTE[5]  # "#FFD700"
        x, y, w, h = 100.0, 50.0, 200.0, 50.0

        # Named action
        env1 = MarketCanvasEnv(prompt=PROMPT, action_mode="high_level")
        env1.reset()
        env1.execute_named_action("add_text", x=x, y=y, width=w, height=h,
                                   color=color, content=text)

        # Numeric action
        env2 = MarketCanvasEnv(prompt=PROMPT, action_mode="high_level")
        env2.reset()
        env2.step({
            "action_type": 0,
            "x": np.float32(x),
            "y": np.float32(y),
            "width": np.float32(w),
            "height": np.float32(h),
            "color_idx": 5,
            "element_idx": 0,
            "text_idx": 0,
        })

        el1 = env1.canvas.elements[0]
        el2 = env2.canvas.elements[0]
        assert el1.x == el2.x
        assert el1.y == el2.y
        assert el1.width == el2.width
        assert el1.height == el2.height
        assert el1.color == el2.color
        assert el1.content == el2.content


# ── Render ────────────────────────────────────────────────────────


class TestRender:
    def test_render_rgb_array(self):
        env = MarketCanvasEnv(prompt=PROMPT, render_mode="rgb_array")
        env.reset()
        arr = env.render()
        assert arr.shape == (600, 800, 3)
        assert arr.dtype == np.uint8

    def test_render_none_mode(self):
        env = MarketCanvasEnv(prompt=PROMPT, render_mode=None)
        env.reset()
        assert env.render() is None


# ── Random agent smoke test ───────────────────────────────────────


class TestRandomAgent:
    @pytest.mark.parametrize("mode", ["high_level", "low_level"])
    def test_random_rollout(self, mode):
        """Random actions for 20 steps without crashing."""
        env = MarketCanvasEnv(prompt=PROMPT, action_mode=mode, max_steps=20)
        obs, info = env.reset()
        for _ in range(20):
            action = env.action_space.sample()
            obs, reward, term, trunc, info = env.step(action)
            assert -1.0 <= reward <= 1.0
            if trunc:
                break
