"""Heuristic reward: constraint satisfaction + aesthetics + accessibility."""

from marketcanvas.canvas import Canvas
from marketcanvas.elements import ImageElement, ShapeElement, TextElement
from marketcanvas.prompt_parser import PromptConstraints
from marketcanvas.wcag import contrast_ratio

# Element type string → class
_TYPE_CLS = {"text": TextElement, "shape": ShapeElement, "image": ImageElement}


class RewardCalculator:
    """Computes a scalar reward in [-1.0, 1.0] from three pillars."""

    W_CONSTRAINT = 0.50
    W_AESTHETICS = 0.25
    W_ACCESSIBILITY = 0.25

    def __init__(self, constraints: PromptConstraints):
        self.constraints = constraints

    def compute(self, canvas: Canvas) -> dict:
        """Return reward breakdown: total + three sub-scores."""
        c = self._constraint_satisfaction(canvas)
        a = self._aesthetics(canvas)
        x = self._accessibility(canvas)

        weighted = self.W_CONSTRAINT * c + self.W_AESTHETICS * a + self.W_ACCESSIBILITY * x
        total = 2 * weighted - 1  # map [0,1] → [-1,1]

        return {
            "total": round(total, 4),
            "constraint_satisfaction": round(c, 4),
            "aesthetics": round(a, 4),
            "accessibility": round(x, 4),
        }

    # ── Constraint satisfaction (50%) ─────────────────────────────

    def _constraint_satisfaction(self, canvas: Canvas) -> float:
        reqs = self.constraints.required_elements
        if not reqs:
            return 1.0  # nothing required → trivially satisfied

        scores = []
        for req in reqs:
            cls = _TYPE_CLS.get(req.element_type)
            best = 0.0
            for el in canvas.elements:
                if not isinstance(el, cls):
                    continue
                best = max(best, self._element_match_score(el, req))
            scores.append(best)
        return sum(scores) / len(scores)

    @staticmethod
    def _element_match_score(el, req) -> float:
        """Score a single element against a requirement: 1.0 / 0.75 / 0.5."""
        # Extract the element's text content
        if isinstance(el, TextElement):
            el_text = el.content.lower()
        elif isinstance(el, ShapeElement):
            el_text = el.text_content.lower()
        elif isinstance(el, ImageElement):
            el_text = el.alt_text.lower()
        else:
            el_text = ""

        # Keyword match
        kw_ok = True
        if req.keywords:
            kw_ok = False
            for kw in req.keywords:
                if kw.lower() in el_text:
                    kw_ok = True
                    break
            if not kw_ok and isinstance(el, TextElement) and "bold" in req.keywords:
                kw_ok = el.bold

        # Color match
        color_ok = req.color_hint is None or el.color.upper() == req.color_hint.upper()

        if kw_ok and color_ok:
            return 1.0
        if kw_ok or color_ok:
            return 0.75
        return 0.5  # type-only match

    # ── Aesthetics (25%) ──────────────────────────────────────────

    def _aesthetics(self, canvas: Canvas) -> float:
        els = canvas.elements
        if not els:
            return 0.0

        n = len(els)

        # Overlap penalty (30%)
        overlap_score = 1.0
        if n > 1:
            pairs = bad = 0
            for i in range(n):
                for j in range(i + 1, n):
                    pairs += 1
                    if els[i].overlaps(els[j]):
                        bad += 1
            overlap_score = 1.0 - (bad / pairs)

        # Horizontal alignment to center (30%)
        cx_canvas = canvas.width / 2
        align_score = sum(
            max(0.0, 1.0 - abs(el.center()[0] - cx_canvas) / cx_canvas)
            for el in els
        ) / n

        # Bounds check (20%)
        bounds_score = sum(
            1.0
            for el in els
            if el.x >= 0
            and el.y >= 0
            and el.x + el.width <= canvas.width
            and el.y + el.height <= canvas.height
        ) / n

        # Vertical spacing consistency (20%)
        spacing_score = 1.0
        if n >= 2:
            sorted_cy = sorted(el.center()[1] for el in els)
            gaps = [sorted_cy[i + 1] - sorted_cy[i] for i in range(len(sorted_cy) - 1)]
            if len(gaps) >= 2:
                avg = sum(gaps) / len(gaps)
                if avg > 0:
                    dev = sum(abs(g - avg) / avg for g in gaps) / len(gaps)
                    spacing_score = max(0.0, 1.0 - dev)

        return (
            0.30 * overlap_score
            + 0.30 * align_score
            + 0.20 * bounds_score
            + 0.20 * spacing_score
        )

    # ── Accessibility (25%) ───────────────────────────────────────

    def _accessibility(self, canvas: Canvas) -> float:
        scores: list[float] = []
        for el in canvas.elements:
            if isinstance(el, TextElement):
                fg, bg = el.text_color, el.color
            elif isinstance(el, ShapeElement) and el.text_content:
                fg, bg = el.text_color, el.color
            else:
                continue

            ratio = contrast_ratio(fg, bg)
            if ratio >= 4.5:
                scores.append(1.0)
            elif ratio >= 3.0:
                scores.append(0.5)
            else:
                scores.append(0.0)

        return sum(scores) / len(scores) if scores else 1.0
