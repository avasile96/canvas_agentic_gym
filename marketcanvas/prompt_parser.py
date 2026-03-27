"""Parse target prompts into PromptConstraints via keyword matching."""

import re
from dataclasses import dataclass, field

COLOR_MAP: dict[str, str] = {
    "red": "#FF0000",
    "blue": "#0000FF",
    "green": "#00FF00",
    "yellow": "#FFD700",
    "orange": "#FF8C00",
    "purple": "#800080",
    "pink": "#FF69B4",
    "black": "#000000",
    "white": "#FFFFFF",
    "gray": "#808080",
    "grey": "#808080",
    "dark": "#333333",
    "gold": "#FFD700",
}

_ELEMENT_TRIGGERS: dict[str, list[str]] = {
    "text": ["headline", "heading", "title", "header", "text", "subtext", "subtitle"],
    "shape": ["button", "cta", "call to action", "call-to-action"],
    "image": ["image", "photo", "picture", "illustration", "graphic", "logo"],
}


@dataclass
class ElementRequirement:
    element_type: str  # "text", "shape", "image"
    keywords: list[str] = field(default_factory=list)
    color_hint: str | None = None


@dataclass
class PromptConstraints:
    required_elements: list[ElementRequirement] = field(default_factory=list)
    color_hints: list[str] = field(default_factory=list)
    content_keywords: list[str] = field(default_factory=list)
    layout_preferences: list[str] = field(default_factory=list)


def parse_prompt(text: str) -> PromptConstraints:
    """Extract design constraints from a natural-language prompt."""
    lower = text.lower()
    constraints = PromptConstraints()

    # Quoted strings → content keywords
    constraints.content_keywords = re.findall(r"['\"]([^'\"]+)['\"]", text)

    # Required elements (one per type, first trigger wins)
    for etype, triggers in _ELEMENT_TRIGGERS.items():
        for trigger in triggers:
            if trigger not in lower:
                continue
            pos = lower.index(trigger)
            window = lower[max(0, pos - 30) : pos + len(trigger) + 30]

            # Color hint — only look at short prefix before trigger
            color_hint = None
            pre = lower[max(0, pos - 15) : pos]
            for word, hex_val in COLOR_MAP.items():
                if word in pre:
                    color_hint = hex_val
                    break

            # Keywords near trigger
            keywords: list[str] = []
            if "bold" in window:
                keywords.append("bold")
            if etype in ("text", "shape"):
                for kw in constraints.content_keywords:
                    if kw.lower() in window:
                        keywords.append(kw)

            constraints.required_elements.append(
                ElementRequirement(etype, keywords, color_hint)
            )
            break

    # Global color hints
    for word, hex_val in COLOR_MAP.items():
        if word in lower and hex_val not in constraints.color_hints:
            constraints.color_hints.append(hex_val)

    # Layout preferences
    for pref in ["centered", "center", "banner", "email", "card"]:
        if pref in lower:
            constraints.layout_preferences.append(pref)

    return constraints
