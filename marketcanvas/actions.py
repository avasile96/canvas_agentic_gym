"""Action interpreters for high-level and low-level canvas manipulation."""

from marketcanvas.canvas import Canvas
from marketcanvas.elements import (
    CanvasElement,
    ImageElement,
    ShapeElement,
    ShapeKind,
    TextElement,
)

# 16-color palette for RL color selection
COLOR_PALETTE = [
    "#FFFFFF", "#000000", "#FF0000", "#00FF00", "#0000FF", "#FFD700",
    "#FF8C00", "#800080", "#FF69B4", "#333333", "#666666", "#999999",
    "#1A1A1A", "#F5F5F5", "#2196F3", "#4CAF50",
]

# Predefined text options for RL text selection
TEXT_OPTIONS = [
    "Sale!", "Shop Now", "Buy Now", "Learn More", "Subscribe",
    "Summer Sale", "New Arrival", "Limited Offer", "Free Shipping", "Click Here",
]


class LowLevelActionInterpreter:
    """Translates low-level mouse/keyboard actions into canvas operations."""

    def __init__(self, canvas: Canvas):
        self.canvas = canvas
        self.cursor_x: float = 0.0
        self.cursor_y: float = 0.0

    def mouse_click(self, x: float, y: float) -> bool:
        """Click at (x, y): hit-test and select element."""
        self.cursor_x, self.cursor_y = x, y
        hit = self.canvas.hit_test(x, y)
        self.canvas.select(hit.id if hit else None)
        return hit is not None

    def mouse_drag(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """Drag from (x1,y1) to (x2,y2): select at start, move by delta."""
        self.cursor_x, self.cursor_y = x2, y2
        hit = self.canvas.hit_test(x1, y1)
        if hit is None:
            return False
        self.canvas.select(hit.id)
        dx, dy = x2 - x1, y2 - y1
        return self.canvas.move_element(hit.id, hit.x + dx, hit.y + dy)

    def mouse_move(self, x: float, y: float) -> None:
        """Move cursor without interaction."""
        self.cursor_x, self.cursor_y = x, y

    def keyboard_type(self, text: str) -> bool:
        """Type text into the selected element."""
        sel = self.canvas.get_selected()
        if sel is None:
            return False
        return self.canvas.change_text(sel.id, text)


def execute_high_level(canvas: Canvas, action_type: str, **params) -> bool:
    """Execute a named high-level action on the canvas.

    Action types:
        add_text, add_shape, add_image, remove, move, resize, change_color, change_text
    """
    if action_type == "add_text":
        el = TextElement(
            x=params.get("x", 0),
            y=params.get("y", 0),
            width=params.get("width", 200),
            height=params.get("height", 50),
            color=params.get("color", "#FFFFFF"),
            content=params.get("content", "Text"),
            text_color=params.get("text_color", "#000000"),
            font_size=params.get("font_size", 16),
            bold=params.get("bold", False),
        )
        return canvas.add_element(el)

    if action_type == "add_shape":
        el = ShapeElement(
            x=params.get("x", 0),
            y=params.get("y", 0),
            width=params.get("width", 150),
            height=params.get("height", 50),
            color=params.get("color", "#FFFFFF"),
            shape_kind=ShapeKind(params.get("shape_kind", "rectangle")),
            text_content=params.get("text_content", ""),
            text_color=params.get("text_color", "#000000"),
            border_radius=params.get("border_radius", 0),
        )
        return canvas.add_element(el)

    if action_type == "add_image":
        el = ImageElement(
            x=params.get("x", 0),
            y=params.get("y", 0),
            width=params.get("width", 200),
            height=params.get("height", 150),
            color=params.get("color", "#E0E0E0"),
            alt_text=params.get("alt_text", "Image"),
        )
        return canvas.add_element(el)

    if action_type == "remove":
        eid = params.get("element_id", "")
        return canvas.remove_element(eid)

    if action_type == "move":
        return canvas.move_element(
            params.get("element_id", ""),
            params.get("x", 0),
            params.get("y", 0),
        )

    if action_type == "resize":
        return canvas.resize_element(
            params.get("element_id", ""),
            params.get("width", 100),
            params.get("height", 50),
        )

    if action_type == "change_color":
        return canvas.change_color(
            params.get("element_id", ""),
            params.get("color", "#FFFFFF"),
        )

    if action_type == "change_text":
        return canvas.change_text(
            params.get("element_id", ""),
            params.get("text", ""),
        )

    return False
