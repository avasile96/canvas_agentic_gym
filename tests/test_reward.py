"""Tests for prompt parser and reward calculator."""

import pytest

from marketcanvas.canvas import Canvas
from marketcanvas.elements import ImageElement, ShapeElement, ShapeKind, TextElement
from marketcanvas.prompt_parser import parse_prompt
from marketcanvas.reward import RewardCalculator


# ── Prompt parser ─────────────────────────────────────────────────


class TestPromptParser:
    def test_extracts_headline(self):
        c = parse_prompt("Create a banner with a bold headline")
        types = [r.element_type for r in c.required_elements]
        assert "text" in types

    def test_extracts_button(self):
        c = parse_prompt("Add a CTA button that says 'Buy Now'")
        types = [r.element_type for r in c.required_elements]
        assert "shape" in types

    def test_extracts_image(self):
        c = parse_prompt("Include a product image")
        types = [r.element_type for r in c.required_elements]
        assert "image" in types

    def test_extracts_all_three(self):
        c = parse_prompt("headline, button, and image")
        types = {r.element_type for r in c.required_elements}
        assert types == {"text", "shape", "image"}

    def test_extracts_color_hints(self):
        c = parse_prompt("yellow background with a blue button")
        assert len(c.color_hints) >= 2

    def test_extracts_quoted_content(self):
        c = parse_prompt("button that says 'Shop Now'")
        assert "Shop Now" in c.content_keywords

    def test_layout_preferences(self):
        c = parse_prompt("a centered email banner")
        assert "centered" in c.layout_preferences
        assert "banner" in c.layout_preferences

    def test_empty_prompt(self):
        c = parse_prompt("")
        assert c.required_elements == []
        assert c.color_hints == []

    def test_color_hint_near_element(self):
        c = parse_prompt("a yellow CTA button")
        shape_reqs = [r for r in c.required_elements if r.element_type == "shape"]
        assert shape_reqs[0].color_hint == "#FFD700"

    def test_bold_keyword(self):
        c = parse_prompt("a bold headline")
        text_reqs = [r for r in c.required_elements if r.element_type == "text"]
        assert "bold" in text_reqs[0].keywords


# ── Reward: edge cases ────────────────────────────────────────────


class TestRewardEdgeCases:
    def test_empty_canvas_minimum_reward(self):
        calc = RewardCalculator(parse_prompt("headline and button"))
        result = calc.compute(Canvas())
        assert result["total"] <= -0.5

    def test_no_constraints_empty_canvas(self):
        calc = RewardCalculator(parse_prompt(""))
        result = calc.compute(Canvas())
        assert result["constraint_satisfaction"] == 1.0

    def test_single_element_canvas(self):
        calc = RewardCalculator(parse_prompt("headline"))
        c = Canvas()
        c.add_element(
            TextElement(id="h", x=350, y=275, width=100, height=50, content="Hi")
        )
        result = calc.compute(c)
        assert result["total"] > -1.0  # better than empty


# ── Reward: constraint satisfaction ───────────────────────────────


class TestConstraintSatisfaction:
    def test_perfect_match(self):
        calc = RewardCalculator(
            parse_prompt(
                "bold headline, yellow button that says 'Shop Now', product image"
            )
        )
        c = Canvas()
        c.add_element(TextElement(id="h", content="Sale!", bold=True))
        c.add_element(
            ShapeElement(
                id="b", color="#FFD700", text_content="Shop Now",
                shape_kind=ShapeKind.button,
            )
        )
        c.add_element(ImageElement(id="i", alt_text="Product"))
        result = calc.compute(c)
        assert result["constraint_satisfaction"] == 1.0

    def test_type_only_match(self):
        calc = RewardCalculator(
            parse_prompt("yellow button that says 'Shop Now'")
        )
        c = Canvas()
        # Shape with wrong color and no matching text
        c.add_element(ShapeElement(id="b", color="#FF0000", text_content="Go"))
        result = calc.compute(c)
        assert 0.0 < result["constraint_satisfaction"] < 1.0

    def test_missing_element(self):
        calc = RewardCalculator(parse_prompt("headline and image"))
        c = Canvas()
        c.add_element(TextElement(id="h", content="Hello"))
        # Missing image
        result = calc.compute(c)
        assert result["constraint_satisfaction"] < 1.0


# ── Reward: aesthetics ────────────────────────────────────────────


class TestAesthetics:
    def test_overlap_penalized(self):
        calc = RewardCalculator(parse_prompt("headline"))
        # No overlap
        c1 = Canvas()
        c1.add_element(TextElement(id="a", x=0, y=0, width=100, height=50))
        c1.add_element(TextElement(id="b", x=0, y=100, width=100, height=50))
        # Full overlap
        c2 = Canvas()
        c2.add_element(TextElement(id="a", x=0, y=0, width=100, height=100))
        c2.add_element(TextElement(id="b", x=0, y=0, width=100, height=100))

        assert calc.compute(c1)["aesthetics"] > calc.compute(c2)["aesthetics"]

    def test_centered_better_than_edge(self):
        calc = RewardCalculator(parse_prompt("headline"))
        # Centered
        c1 = Canvas()
        c1.add_element(TextElement(id="a", x=350, y=275, width=100, height=50))
        # At left edge
        c2 = Canvas()
        c2.add_element(TextElement(id="a", x=0, y=275, width=100, height=50))

        assert calc.compute(c1)["aesthetics"] > calc.compute(c2)["aesthetics"]

    def test_out_of_bounds_penalized(self):
        calc = RewardCalculator(parse_prompt("headline"))
        # In bounds
        c1 = Canvas()
        c1.add_element(TextElement(id="a", x=100, y=100, width=100, height=50))
        # Out of bounds
        c2 = Canvas()
        c2.add_element(TextElement(id="a", x=750, y=100, width=100, height=50))

        assert calc.compute(c1)["aesthetics"] > calc.compute(c2)["aesthetics"]


# ── Reward: accessibility ─────────────────────────────────────────


class TestAccessibility:
    def test_good_contrast(self):
        calc = RewardCalculator(parse_prompt("headline"))
        c = Canvas()
        c.add_element(
            TextElement(id="t", content="Hi", text_color="#000000", color="#FFFFFF")
        )
        assert calc.compute(c)["accessibility"] == 1.0

    def test_bad_contrast(self):
        calc = RewardCalculator(parse_prompt("headline"))
        c = Canvas()
        c.add_element(
            TextElement(id="t", content="Hi", text_color="#FFFFFF", color="#FFFFFF")
        )
        assert calc.compute(c)["accessibility"] == 0.0

    def test_medium_contrast(self):
        calc = RewardCalculator(parse_prompt("headline"))
        c = Canvas()
        # #808080 on white ≈ 3.95:1 — between 3.0 and 4.5
        c.add_element(
            TextElement(id="t", content="Hi", text_color="#808080", color="#FFFFFF")
        )
        assert calc.compute(c)["accessibility"] == 0.5

    def test_shape_text_checked(self):
        calc = RewardCalculator(parse_prompt("button"))
        c = Canvas()
        c.add_element(
            ShapeElement(
                id="b", text_content="Go", text_color="#000000", color="#FFFFFF"
            )
        )
        assert calc.compute(c)["accessibility"] == 1.0

    def test_shape_without_text_skipped(self):
        calc = RewardCalculator(parse_prompt("button"))
        c = Canvas()
        c.add_element(ShapeElement(id="b", text_content=""))
        assert calc.compute(c)["accessibility"] == 1.0


# ── Reward: full pipeline ────────────────────────────────────────


class TestRewardFullPipeline:
    def test_good_banner_high_reward(self):
        calc = RewardCalculator(
            parse_prompt(
                "Create a banner with a bold headline, "
                "a yellow CTA button that says 'Shop Now', "
                "and a product image"
            )
        )
        c = Canvas()
        c.add_element(
            TextElement(
                id="h", x=250, y=30, width=300, height=50,
                content="Summer Sale!", text_color="#000000", color="#FFFFFF",
                bold=True, font_size=32,
            )
        )
        c.add_element(
            ImageElement(
                id="img", x=250, y=120, width=300, height=200,
                alt_text="Product Image",
            )
        )
        c.add_element(
            ShapeElement(
                id="cta", x=300, y=380, width=200, height=60,
                shape_kind=ShapeKind.button, color="#FFD700",
                text_content="Shop Now", text_color="#000000",
            )
        )
        result = calc.compute(c)
        assert result["total"] > 0.5
        assert result["constraint_satisfaction"] >= 0.9
        assert result["aesthetics"] > 0.8
        assert result["accessibility"] == 1.0
