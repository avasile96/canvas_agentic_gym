"""WCAG 2.1 contrast ratio utilities."""


def _srgb_to_linear(c: float) -> float:
    """Convert sRGB channel value (0-1) to linear RGB."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse hex color string to (r, g, b)."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def relative_luminance(r: int, g: int, b: int) -> float:
    """Relative luminance per WCAG 2.1. Inputs are 0-255."""
    rs, gs, bs = r / 255, g / 255, b / 255
    return (
        0.2126 * _srgb_to_linear(rs)
        + 0.7152 * _srgb_to_linear(gs)
        + 0.0722 * _srgb_to_linear(bs)
    )


def contrast_ratio(hex1: str, hex2: str) -> float:
    """Contrast ratio between two hex colors (always >= 1.0)."""
    l1 = relative_luminance(*hex_to_rgb(hex1))
    l2 = relative_luminance(*hex_to_rgb(hex2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def meets_aa(hex_fg: str, hex_bg: str, large_text: bool = False) -> bool:
    """Check WCAG 2.1 AA compliance. Normal text: 4.5:1, large text: 3:1."""
    ratio = contrast_ratio(hex_fg, hex_bg)
    return ratio >= (3.0 if large_text else 4.5)
