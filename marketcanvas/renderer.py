"""PIL-based canvas renderer."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from marketcanvas.canvas import Canvas
from marketcanvas.elements import ImageElement, ShapeElement, TextElement


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try system TrueType fonts, fall back to PIL default."""
    names = (
        ["Helvetica-Bold", "DejaVuSans-Bold", "arialbd"]
        if bold
        else ["Helvetica", "DejaVuSans", "arial"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[int, int, int, int],
    color: str = "#2196F3",
    dash: int = 6,
    gap: int = 4,
    width: int = 2,
) -> None:
    """Draw a dashed rectangle border."""
    x1, y1, x2, y2 = bbox
    sides = [
        (x1, y1, x2, y1, True),
        (x1, y2, x2, y2, True),
        (x1, y1, x1, y2, False),
        (x2, y1, x2, y2, False),
    ]
    for sx, sy, ex, ey, horiz in sides:
        length = abs(ex - sx) if horiz else abs(ey - sy)
        pos = 0
        while pos < length:
            end = min(pos + dash, length)
            if horiz:
                draw.line([(sx + pos, sy), (sx + end, sy)], fill=color, width=width)
            else:
                draw.line([(sx, sy + pos), (sx, sy + end)], fill=color, width=width)
            pos += dash + gap


class CanvasRenderer:
    """Renders a Canvas to a PIL Image."""

    def __init__(self, canvas: Canvas):
        self.canvas = canvas

    def render(self) -> Image.Image:
        """Render canvas to PIL Image."""
        c = self.canvas
        img = Image.new("RGB", (c.width, c.height), c.background_color)
        draw = ImageDraw.Draw(img)

        for el in sorted(c.elements, key=lambda e: e.z_index):
            x1, y1, x2, y2 = (int(v) for v in el.bbox())

            if isinstance(el, TextElement):
                draw.rectangle((x1, y1, x2, y2), fill=el.color)
                font = _load_font(el.font_size, el.bold)
                draw.text((x1 + 4, y1 + 4), el.content, fill=el.text_color, font=font)

            elif isinstance(el, ShapeElement):
                if el.border_radius > 0:
                    draw.rounded_rectangle(
                        (x1, y1, x2, y2), radius=el.border_radius, fill=el.color
                    )
                else:
                    draw.rectangle((x1, y1, x2, y2), fill=el.color)
                if el.text_content:
                    font = _load_font(max(12, int(el.height * 0.4)))
                    tb = draw.textbbox((0, 0), el.text_content, font=font)
                    tw, th = tb[2] - tb[0], tb[3] - tb[1]
                    draw.text(
                        (x1 + (el.width - tw) // 2, y1 + (el.height - th) // 2),
                        el.text_content,
                        fill=el.text_color,
                        font=font,
                    )

            elif isinstance(el, ImageElement):
                draw.rectangle((x1, y1, x2, y2), fill=el.color, outline="#999999")
                draw.line([(x1, y1), (x2, y2)], fill="#999999")
                draw.line([(x2, y1), (x1, y2)], fill="#999999")
                font = _load_font(12)
                draw.text((x1 + 4, y1 + 4), el.alt_text, fill="#666666", font=font)

            # Blue dashed border on selected element
            if el.id == c._selected_id:
                _draw_dashed_rect(draw, (x1 - 2, y1 - 2, x2 + 2, y2 + 2))

        return img

    def render_to_array(self) -> np.ndarray:
        """Render to numpy array shape (H, W, 3) uint8."""
        return np.array(self.render())

    def save_png(self, path: str | Path) -> None:
        """Render and save as PNG."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.render().save(str(path), "PNG")
