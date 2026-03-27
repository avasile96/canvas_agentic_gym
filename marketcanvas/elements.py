"""Pydantic models for canvas elements."""

from enum import Enum
from pydantic import BaseModel, Field
import uuid


class ShapeKind(str, Enum):
    rectangle = "rectangle"
    button = "button"


class CanvasElement(BaseModel):
    """Base canvas element with position, size, and style."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 50.0
    z_index: int = 0
    color: str = "#FFFFFF"

    def bbox(self) -> tuple[float, float, float, float]:
        """Return (x1, y1, x2, y2) bounding box."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def center(self) -> tuple[float, float]:
        """Return (cx, cy) center point."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    def overlaps(self, other: "CanvasElement") -> bool:
        """Check if this element overlaps with another."""
        x1, y1, x2, y2 = self.bbox()
        ox1, oy1, ox2, oy2 = other.bbox()
        return x1 < ox2 and x2 > ox1 and y1 < oy2 and y2 > oy1

    def overlap_area(self, other: "CanvasElement") -> float:
        """Calculate overlap area between two elements."""
        x1, y1, x2, y2 = self.bbox()
        ox1, oy1, ox2, oy2 = other.bbox()
        dx = min(x2, ox2) - max(x1, ox1)
        dy = min(y2, oy2) - max(y1, oy1)
        if dx <= 0 or dy <= 0:
            return 0.0
        return dx * dy


class TextElement(CanvasElement):
    """Text element with typography properties."""

    type: str = "text"
    content: str = "Text"
    text_color: str = "#000000"
    font_size: int = 16
    bold: bool = False


class ShapeElement(CanvasElement):
    """Shape element (rectangle or button)."""

    type: str = "shape"
    shape_kind: ShapeKind = ShapeKind.rectangle
    border_radius: int = 0
    text_content: str = ""
    text_color: str = "#000000"


class ImageElement(CanvasElement):
    """Image placeholder element."""

    type: str = "image"
    alt_text: str = "Image"
