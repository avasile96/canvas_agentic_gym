"""Perturbation-based reward validation.

A well-formed banner degrades monotonically under controlled degradations,
mirroring DesignSense's augmentation strategy (arXiv 2602.23438).
"""

import random

import pytest

from marketcanvas.canvas import Canvas
from marketcanvas.elements import ImageElement, ShapeElement, ShapeKind, TextElement
from marketcanvas.prompt_parser import parse_prompt
from marketcanvas.reward import RewardCalculator

_PROMPT = (
    "Create a Summer Sale email banner with a bold headline, "
    "a yellow CTA button that says 'Shop Now', and a product image"
)


def _good_banner() -> Canvas:
    """A well-laid-out banner that should score above zero."""
    canvas = Canvas(background_color="#1A1A2E")
    canvas.add_element(
        TextElement(
            content="Summer Sale",
            font_size=36,
            bold=True,
            text_color="#FFFFFF",
            x=200,
            y=80,
            width=400,
            height=60,
            z_index=1,
        )
    )
    canvas.add_element(
        TextElement(
            content="Up to 50% off",
            font_size=20,
            text_color="#CCCCCC",
            x=250,
            y=160,
            width=300,
            height=40,
            z_index=2,
        )
    )
    canvas.add_element(
        ImageElement(
            alt_text="product image",
            x=300,
            y=220,
            width=200,
            height=150,
            z_index=3,
        )
    )
    canvas.add_element(
        ShapeElement(
            shape_kind=ShapeKind.button,
            text_content="Shop Now",
            color="#FFD700",
            text_color="#000000",
            x=300,
            y=400,
            width=200,
            height=50,
            z_index=4,
        )
    )
    return canvas


@pytest.fixture
def calc():
    return RewardCalculator(parse_prompt(_PROMPT))


def test_good_banner_positive_reward(calc):
    assert calc.compute(_good_banner())["total"] > 0.0


def test_heavy_overlap_reduces_reward(calc):
    baseline = calc.compute(_good_banner())["total"]
    canvas = _good_banner()
    for el in canvas.elements:
        el.x = 100
        el.y = 100
    assert calc.compute(canvas)["total"] < baseline


def test_offscreen_elements_reduce_reward(calc):
    baseline = calc.compute(_good_banner())["total"]
    canvas = _good_banner()
    for el in canvas.elements:
        el.x = 900  # beyond 800px canvas width
    assert calc.compute(canvas)["total"] < baseline


def test_poor_contrast_reduces_reward(calc):
    baseline = calc.compute(_good_banner())["total"]
    canvas = _good_banner()
    for el in canvas.elements:
        if isinstance(el, TextElement):
            el.text_color = "#FEFEFE"
            el.color = "#FFFFFF"
        elif isinstance(el, ShapeElement) and el.text_content:
            el.text_color = "#FEFEFE"
            el.color = "#FFFFFF"
    assert calc.compute(canvas)["total"] < baseline


def test_missing_required_elements_reduces_reward(calc):
    sparse = Canvas(background_color="#1A1A2E")
    sparse.add_element(TextElement(content="Hello", x=100, y=100, width=200, height=50))
    assert calc.compute(sparse)["total"] < calc.compute(_good_banner())["total"]


def test_pairwise_comparison_picks_better_layout(calc):
    """Good layout should beat a degraded one — same logic as compare_canvas_states MCP tool."""
    good = _good_banner()
    degraded = _good_banner()
    for el in degraded.elements:
        el.x = 100
        el.y = 100  # stack everything → heavy overlap

    score_good = calc.compute(good)["total"]
    score_bad = calc.compute(degraded)["total"]
    assert score_good > score_bad


def test_random_perturbations_trend_downward(calc):
    """Increasing positional perturbation magnitude should generally decrease reward."""
    rng = random.Random(42)

    def perturb(magnitude: float) -> float:
        canvas = _good_banner()
        for el in canvas.elements:
            el.x = max(0.0, el.x + rng.uniform(-magnitude, magnitude))
            el.y = max(0.0, el.y + rng.uniform(-magnitude, magnitude))
        return calc.compute(canvas)["total"]

    scores = [perturb(m) for m in [0, 40, 100, 200]]
    # Allow at most one inversion in the downward trend
    inversions = sum(1 for i in range(len(scores) - 1) if scores[i] < scores[i + 1])
    assert inversions <= 1, f"Expected mostly downward trend, got: {scores}"
