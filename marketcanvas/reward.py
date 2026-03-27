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

    def compute_with_diagnostics(self, canvas: Canvas) -> dict:
        """Like compute() but adds per-element diagnostic messages for actionable LLM feedback."""
        result = self.compute(canvas)
        diagnostics: list[str] = []
        els = canvas.elements

        # Overlap diagnostics — skip background layers
        canvas_area = canvas.width * canvas.height
        bg_ids = set()
        if len(els) > 1:
            min_z = min(e.z_index for e in els)
            bg_ids = {e.id for e in els if e.z_index == min_z and e.width * e.height >= canvas_area * 0.9}
        for i, a in enumerate(els):
            if a.id in bg_ids:
                continue
            for b in els[i + 1 :]:
                if b.id in bg_ids:
                    continue
                if a.overlaps(b):
                    area = a.overlap_area(b)
                    diagnostics.append(
                        f"{a.id} overlaps {b.id} by {area:.0f}px\u00b2"
                    )

        # Contrast diagnostics
        for el in els:
            if isinstance(el, TextElement):
                fg, bg = el.text_color, el.color
                label = el.content[:20] or el.id
            elif isinstance(el, ShapeElement) and el.text_content:
                fg, bg = el.text_color, el.color
                label = el.text_content[:20] or el.id
            else:
                continue
            ratio = contrast_ratio(fg, bg)
            if ratio < 4.5:
                level = "below AA" if ratio >= 3.0 else "very low contrast"
                diagnostics.append(f'"{label}" contrast ratio {ratio:.1f} \u2014 {level}')

        # Centering diagnostics — only flag elements expected to be centered
        canvas_cx = canvas.width / 2
        for el in els:
            is_headline = isinstance(el, TextElement) and el.bold
            is_cta = isinstance(el, ShapeElement) and el.shape_kind.value == "button"
            if not (is_headline or is_cta):
                continue
            cx = el.center()[0]
            if abs(cx - canvas_cx) >= 10:
                off = cx - canvas_cx
                label = "headline" if is_headline else "CTA"
                diagnostics.append(
                    f"{el.id} ({label}) not horizontally centered (offset {off:+.0f}px)"
                )

        # Visual hierarchy diagnostics
        text_els = [e for e in els if isinstance(e, TextElement)]
        if len(text_els) >= 2:
            headline = self._find_headline(text_els)
            max_area = max(e.width * e.height for e in text_els)
            if headline.width * headline.height < max_area * 0.9:
                diagnostics.append(
                    f"{headline.id} (headline) is not the largest text element — visual hierarchy broken"
                )

        for el in els:
            if isinstance(el, ShapeElement) and el.shape_kind.value == "button":
                if el.width < 80 or el.height < 30:
                    diagnostics.append(
                        f"CTA {el.id} too small ({el.width:.0f}\u00d7{el.height:.0f}px)"
                        " \u2014 minimum 80\u00d730 recommended"
                    )

        result["diagnostics"] = diagnostics
        return result

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

        # Overlap penalty (25%) — ignore background layers (lowest z-index, ≥90% canvas area)
        canvas_area = canvas.width * canvas.height
        bg = set()
        if n > 1:
            min_z = min(e.z_index for e in els)
            bg = {id(e) for e in els if e.z_index == min_z and e.width * e.height >= canvas_area * 0.9}

        overlap_score = 1.0
        if n - len(bg) > 1:
            pairs = bad = 0
            for i in range(n):
                if id(els[i]) in bg:
                    continue
                for j in range(i + 1, n):
                    if id(els[j]) in bg:
                        continue
                    pairs += 1
                    if els[i].overlaps(els[j]):
                        bad += 1
            overlap_score = 1.0 - (bad / pairs) if pairs else 1.0

        # Horizontal alignment to center (25%)
        cx_canvas = canvas.width / 2
        align_score = sum(
            max(0.0, 1.0 - abs(el.center()[0] - cx_canvas) / cx_canvas)
            for el in els
        ) / n

        # Bounds check (15%)
        bounds_score = sum(
            1.0
            for el in els
            if el.x >= 0
            and el.y >= 0
            and el.x + el.width <= canvas.width
            and el.y + el.height <= canvas.height
        ) / n

        # Vertical spacing consistency (15%)
        spacing_score = 1.0
        if n >= 2:
            sorted_cy = sorted(el.center()[1] for el in els)
            gaps = [sorted_cy[i + 1] - sorted_cy[i] for i in range(len(sorted_cy) - 1)]
            if len(gaps) >= 2:
                avg = sum(gaps) / len(gaps)
                if avg > 0:
                    dev = sum(abs(g - avg) / avg for g in gaps) / len(gaps)
                    spacing_score = max(0.0, 1.0 - dev)

        # Visual hierarchy (20%)
        hierarchy_score = self._visual_hierarchy(canvas)

        return (
            0.25 * overlap_score
            + 0.25 * align_score
            + 0.15 * bounds_score
            + 0.15 * spacing_score
            + 0.20 * hierarchy_score
        )

    @staticmethod
    def _find_headline(text_els: list[TextElement]) -> TextElement:
        """Identify the headline: first bold text, or largest font."""
        bold = [e for e in text_els if e.bold]
        return bold[0] if bold else max(text_els, key=lambda e: e.font_size)

    def _visual_hierarchy(self, canvas: Canvas) -> float:
        """Score whether visual size/prominence matches semantic role from the prompt."""
        els = canvas.elements
        if len(els) < 2:
            return 1.0

        checks = hits = 0
        text_els = [e for e in els if isinstance(e, TextElement)]
        button_els = [
            e for e in els if isinstance(e, ShapeElement) and e.shape_kind.value == "button"
        ]

        # Rule 1: Headline (bold or largest font) should be the largest-area text element.
        if len(text_els) >= 2:
            checks += 1
            headline = self._find_headline(text_els)
            max_area = max(e.width * e.height for e in text_els)
            if headline.width * headline.height >= max_area * 0.9:
                hits += 1

        # Rule 2: CTA button should meet minimum clickable size (80×30px).
        if button_els:
            checks += 1
            biggest = max(button_els, key=lambda e: e.width * e.height)
            if biggest.width >= 80 and biggest.height >= 30:
                hits += 1

        # Rule 3: First required element type should not be dominated in area by later types.
        reqs = self.constraints.required_elements
        if len(reqs) >= 2:
            primary_cls = _TYPE_CLS.get(reqs[0].element_type)
            secondary_cls = _TYPE_CLS.get(reqs[1].element_type)
            if primary_cls and secondary_cls and primary_cls is not secondary_cls:
                primary_els = [e for e in els if isinstance(e, primary_cls)]
                secondary_els = [e for e in els if isinstance(e, secondary_cls)]
                if primary_els and secondary_els:
                    checks += 1
                    primary_max = max(e.width * e.height for e in primary_els)
                    secondary_max = max(e.width * e.height for e in secondary_els)
                    if primary_max >= secondary_max * 0.7:
                        hits += 1

        return hits / checks if checks > 0 else 1.0

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
