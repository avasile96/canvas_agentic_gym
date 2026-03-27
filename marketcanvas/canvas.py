"""Core 2D canvas engine with CRUD, hit-testing, and serialization."""

from typing import Optional

from marketcanvas.elements import CanvasElement, TextElement, ShapeElement, ImageElement

MAX_ELEMENTS = 20


class Canvas:
    """800x600 2D canvas with element management."""

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        background_color: str = "#FFFFFF",
    ):
        self.width = width
        self.height = height
        self.background_color = background_color
        self.elements: list[CanvasElement] = []
        self._selected_id: Optional[str] = None

    def add_element(self, element: CanvasElement) -> bool:
        """Add element to canvas. Returns False if at capacity."""
        if len(self.elements) >= MAX_ELEMENTS:
            return False
        if element.z_index == 0 and self.elements:
            element.z_index = max(e.z_index for e in self.elements) + 1
        self.elements.append(element)
        return True

    def remove_element(self, element_id: str) -> bool:
        """Remove element by ID."""
        for i, e in enumerate(self.elements):
            if e.id == element_id:
                self.elements.pop(i)
                if self._selected_id == element_id:
                    self._selected_id = None
                return True
        return False

    def get_element(self, element_id: str) -> Optional[CanvasElement]:
        """Get element by ID."""
        for e in self.elements:
            if e.id == element_id:
                return e
        return None

    def move_element(self, element_id: str, x: float, y: float) -> bool:
        """Move element to absolute position."""
        el = self.get_element(element_id)
        if el is None:
            return False
        el.x = x
        el.y = y
        return True

    def resize_element(self, element_id: str, width: float, height: float) -> bool:
        """Resize element."""
        el = self.get_element(element_id)
        if el is None:
            return False
        el.width = width
        el.height = height
        return True

    def change_color(self, element_id: str, color: str) -> bool:
        """Change element fill color."""
        el = self.get_element(element_id)
        if el is None:
            return False
        el.color = color
        return True

    def change_text(self, element_id: str, text: str) -> bool:
        """Change text content of a text or shape element."""
        el = self.get_element(element_id)
        if el is None:
            return False
        if isinstance(el, TextElement):
            el.content = text
            return True
        if isinstance(el, ShapeElement):
            el.text_content = text
            return True
        return False

    def hit_test(self, x: float, y: float) -> Optional[CanvasElement]:
        """Return topmost element at (x, y) by z-index."""
        hits = []
        for e in self.elements:
            x1, y1, x2, y2 = e.bbox()
            if x1 <= x <= x2 and y1 <= y <= y2:
                hits.append(e)
        if not hits:
            return None
        return max(hits, key=lambda e: e.z_index)

    def select(self, element_id: Optional[str]) -> None:
        """Select element by ID, or deselect with None."""
        self._selected_id = element_id

    def get_selected(self) -> Optional[CanvasElement]:
        """Get currently selected element."""
        if self._selected_id is None:
            return None
        return self.get_element(self._selected_id)

    def to_semantic_state(self) -> dict:
        """Return JSON-serializable semantic DOM of the canvas."""
        canvas_cx = self.width / 2
        sorted_els = sorted(self.elements, key=lambda e: e.z_index)
        elements_data = []

        for el in sorted_els:
            cx, cy = el.center()
            entry = {
                "id": el.id,
                "type": type(el).__name__.replace("Element", "").lower(),
                "x": el.x,
                "y": el.y,
                "width": el.width,
                "height": el.height,
                "z_index": el.z_index,
                "color": el.color,
                "center": {"x": cx, "y": cy},
                "horizontally_centered": abs(cx - canvas_cx) < 10,
            }

            if isinstance(el, TextElement):
                entry.update(
                    content=el.content,
                    text_color=el.text_color,
                    font_size=el.font_size,
                    bold=el.bold,
                )
            elif isinstance(el, ShapeElement):
                entry.update(
                    shape_kind=el.shape_kind.value,
                    text_content=el.text_content,
                    text_color=el.text_color,
                    border_radius=el.border_radius,
                )
            elif isinstance(el, ImageElement):
                entry["alt_text"] = el.alt_text

            # Overlap list
            entry["overlaps_with"] = [
                other.id
                for other in self.elements
                if other.id != el.id and el.overlaps(other)
            ]

            # Nearest neighbors (top 3 by center distance)
            distances = []
            for other in self.elements:
                if other.id == el.id:
                    continue
                ocx, ocy = other.center()
                dist = ((cx - ocx) ** 2 + (cy - ocy) ** 2) ** 0.5
                distances.append({"id": other.id, "distance": round(dist, 1)})
            distances.sort(key=lambda d: d["distance"])
            entry["nearest_neighbors"] = distances[:3]

            elements_data.append(entry)

        return {
            "canvas": {
                "width": self.width,
                "height": self.height,
                "background_color": self.background_color,
                "element_count": len(self.elements),
            },
            "elements": elements_data,
            "groups": self._semantic_groups(sorted_els),
            "selected_id": self._selected_id,
        }

    def _semantic_groups(self, sorted_els: list) -> list[dict]:
        """Group semantically related elements by type and spatial proximity."""
        groups: list[dict] = []
        assigned: set[str] = set()

        # Pass 1: button shapes + any nearby text → call-to-action group
        for el in sorted_els:
            if el.id in assigned:
                continue
            if not (isinstance(el, ShapeElement) and el.shape_kind.value == "button"):
                continue
            cx, cy = el.center()
            close_texts = [
                other for other in sorted_els
                if other.id not in assigned
                and isinstance(other, TextElement)
                and ((cx - other.center()[0]) ** 2 + (cy - other.center()[1]) ** 2) ** 0.5 < 80
            ]
            members = [el.id] + [o.id for o in close_texts]
            for mid in members:
                assigned.add(mid)
            groups.append({"label": "call-to-action", "members": members})

        # Pass 2: vertically close text elements → header group
        for el in sorted_els:
            if el.id in assigned or not isinstance(el, TextElement):
                continue
            _, cy = el.center()
            nearby = [
                other for other in sorted_els
                if other.id != el.id
                and other.id not in assigned
                and isinstance(other, TextElement)
                and abs(cy - other.center()[1]) < 80
            ]
            if nearby:
                members = [el.id] + [o.id for o in nearby]
                for mid in members:
                    assigned.add(mid)
                groups.append({"label": "header", "members": members})
            else:
                assigned.add(el.id)

        return groups
