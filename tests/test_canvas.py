"""Tests for canvas engine and element models."""

import pytest

from marketcanvas.canvas import MAX_ELEMENTS, Canvas
from marketcanvas.elements import (
    ImageElement,
    ShapeElement,
    ShapeKind,
    TextElement,
)


# ── Element geometry ──────────────────────────────────────────────


class TestElementGeometry:
    def test_bbox(self):
        el = TextElement(x=10, y=20, width=100, height=50)
        assert el.bbox() == (10, 20, 110, 70)

    def test_center(self):
        el = TextElement(x=0, y=0, width=100, height=50)
        assert el.center() == (50.0, 25.0)

    def test_overlaps_true(self):
        a = TextElement(x=0, y=0, width=100, height=100)
        b = TextElement(x=50, y=50, width=100, height=100)
        assert a.overlaps(b) is True
        assert b.overlaps(a) is True

    def test_overlaps_false(self):
        a = TextElement(x=0, y=0, width=100, height=100)
        b = TextElement(x=200, y=200, width=100, height=100)
        assert a.overlaps(b) is False

    def test_edge_touching_no_overlap(self):
        a = TextElement(x=0, y=0, width=100, height=100)
        b = TextElement(x=100, y=0, width=100, height=100)
        assert a.overlaps(b) is False

    def test_overlap_area(self):
        a = TextElement(x=0, y=0, width=100, height=100)
        b = TextElement(x=50, y=50, width=100, height=100)
        assert a.overlap_area(b) == 2500.0

    def test_overlap_area_none(self):
        a = TextElement(x=0, y=0, width=100, height=100)
        b = TextElement(x=200, y=200, width=100, height=100)
        assert a.overlap_area(b) == 0.0


# ── Element types ─────────────────────────────────────────────────


class TestElementTypes:
    def test_text_defaults(self):
        el = TextElement()
        assert el.type == "text"
        assert el.content == "Text"
        assert el.font_size == 16
        assert el.bold is False

    def test_shape_button(self):
        el = ShapeElement(shape_kind=ShapeKind.button, text_content="Click")
        assert el.shape_kind == ShapeKind.button
        assert el.text_content == "Click"

    def test_image_element(self):
        el = ImageElement(alt_text="Product photo")
        assert el.type == "image"
        assert el.alt_text == "Product photo"

    def test_unique_ids(self):
        a = TextElement()
        b = TextElement()
        assert a.id != b.id


# ── Canvas CRUD ───────────────────────────────────────────────────


class TestCanvasCrud:
    def test_defaults(self):
        c = Canvas()
        assert c.width == 800
        assert c.height == 600
        assert c.background_color == "#FFFFFF"

    def test_add_element(self):
        c = Canvas()
        assert c.add_element(TextElement(content="Hi")) is True
        assert len(c.elements) == 1

    def test_max_capacity(self):
        c = Canvas()
        for i in range(MAX_ELEMENTS):
            c.add_element(TextElement(content=f"El {i}"))
        assert c.add_element(TextElement()) is False
        assert len(c.elements) == MAX_ELEMENTS

    def test_remove(self):
        c = Canvas()
        el = TextElement(id="rm")
        c.add_element(el)
        assert c.remove_element("rm") is True
        assert len(c.elements) == 0

    def test_remove_nonexistent(self):
        c = Canvas()
        assert c.remove_element("nope") is False

    def test_remove_clears_selection(self):
        c = Canvas()
        el = TextElement(id="sel")
        c.add_element(el)
        c.select("sel")
        c.remove_element("sel")
        assert c.get_selected() is None

    def test_move(self):
        c = Canvas()
        el = TextElement(id="mv", x=0, y=0)
        c.add_element(el)
        assert c.move_element("mv", 100, 200) is True
        assert el.x == 100 and el.y == 200

    def test_move_nonexistent(self):
        assert Canvas().move_element("x", 0, 0) is False

    def test_resize(self):
        c = Canvas()
        el = TextElement(id="rs", width=100, height=50)
        c.add_element(el)
        c.resize_element("rs", 200, 100)
        assert el.width == 200 and el.height == 100

    def test_change_color(self):
        c = Canvas()
        el = TextElement(id="cc", color="#FFFFFF")
        c.add_element(el)
        c.change_color("cc", "#FF0000")
        assert el.color == "#FF0000"

    def test_change_text_on_text(self):
        c = Canvas()
        el = TextElement(id="ct", content="Old")
        c.add_element(el)
        assert c.change_text("ct", "New") is True
        assert el.content == "New"

    def test_change_text_on_shape(self):
        c = Canvas()
        el = ShapeElement(id="cs", text_content="Old")
        c.add_element(el)
        assert c.change_text("cs", "New") is True
        assert el.text_content == "New"

    def test_change_text_on_image_fails(self):
        c = Canvas()
        el = ImageElement(id="ci")
        c.add_element(el)
        assert c.change_text("ci", "text") is False


# ── Hit testing ───────────────────────────────────────────────────


class TestHitTest:
    def test_basic_hit(self):
        c = Canvas()
        el = TextElement(id="ht", x=10, y=10, width=100, height=50)
        c.add_element(el)
        assert c.hit_test(50, 30) == el

    def test_miss(self):
        c = Canvas()
        c.add_element(TextElement(x=10, y=10, width=100, height=50))
        assert c.hit_test(500, 500) is None

    def test_z_order_topmost(self):
        c = Canvas()
        bottom = TextElement(id="bot", x=0, y=0, width=100, height=100, z_index=1)
        top = TextElement(id="top", x=0, y=0, width=100, height=100, z_index=10)
        c.add_element(bottom)
        c.add_element(top)
        assert c.hit_test(50, 50).id == "top"

    def test_empty_canvas(self):
        assert Canvas().hit_test(50, 50) is None


# ── Selection ─────────────────────────────────────────────────────


class TestSelection:
    def test_select_and_get(self):
        c = Canvas()
        el = TextElement(id="s1")
        c.add_element(el)
        c.select("s1")
        assert c.get_selected() == el

    def test_deselect(self):
        c = Canvas()
        el = TextElement(id="s1")
        c.add_element(el)
        c.select("s1")
        c.select(None)
        assert c.get_selected() is None


# ── Auto z-index ──────────────────────────────────────────────────


class TestAutoZIndex:
    def test_auto_increments(self):
        c = Canvas()
        a = TextElement(id="a")
        b = TextElement(id="b")
        c.add_element(a)
        c.add_element(b)
        assert b.z_index > a.z_index

    def test_explicit_z_preserved(self):
        c = Canvas()
        c.add_element(TextElement(id="a"))
        b = TextElement(id="b", z_index=99)
        c.add_element(b)
        assert b.z_index == 99


# ── Semantic state ────────────────────────────────────────────────


class TestSemanticState:
    def test_structure(self):
        c = Canvas()
        c.add_element(TextElement(id="t1", content="Hello", x=350, y=100, width=100, height=30))
        state = c.to_semantic_state()
        assert state["canvas"]["width"] == 800
        assert state["canvas"]["element_count"] == 1
        el = state["elements"][0]
        assert el["id"] == "t1"
        assert el["type"] == "text"
        assert el["content"] == "Hello"

    def test_horizontally_centered(self):
        c = Canvas()
        # cx = 350 + 100/2 = 400 = canvas center
        c.add_element(TextElement(id="ctr", x=350, y=100, width=100, height=30))
        state = c.to_semantic_state()
        assert state["elements"][0]["horizontally_centered"] is True

    def test_not_centered(self):
        c = Canvas()
        c.add_element(TextElement(id="off", x=10, y=100, width=100, height=30))
        state = c.to_semantic_state()
        assert state["elements"][0]["horizontally_centered"] is False

    def test_overlaps_reported(self):
        c = Canvas()
        c.add_element(TextElement(id="a", x=0, y=0, width=100, height=100))
        c.add_element(TextElement(id="b", x=50, y=50, width=100, height=100))
        state = c.to_semantic_state()
        a_data = next(e for e in state["elements"] if e["id"] == "a")
        assert "b" in a_data["overlaps_with"]

    def test_nearest_neighbors(self):
        c = Canvas()
        c.add_element(TextElement(id="a", x=0, y=0, width=10, height=10))
        c.add_element(TextElement(id="b", x=100, y=0, width=10, height=10))
        c.add_element(TextElement(id="c", x=500, y=0, width=10, height=10))
        state = c.to_semantic_state()
        a_data = next(e for e in state["elements"] if e["id"] == "a")
        assert a_data["nearest_neighbors"][0]["id"] == "b"

    def test_selected_id(self):
        c = Canvas()
        c.add_element(TextElement(id="sel"))
        c.select("sel")
        state = c.to_semantic_state()
        assert state["selected_id"] == "sel"

    def test_shape_fields(self):
        c = Canvas()
        c.add_element(ShapeElement(id="sh", shape_kind=ShapeKind.button, text_content="Go"))
        state = c.to_semantic_state()
        el = state["elements"][0]
        assert el["type"] == "shape"
        assert el["shape_kind"] == "button"
        assert el["text_content"] == "Go"

    def test_image_fields(self):
        c = Canvas()
        c.add_element(ImageElement(id="img", alt_text="Product"))
        state = c.to_semantic_state()
        assert state["elements"][0]["alt_text"] == "Product"
