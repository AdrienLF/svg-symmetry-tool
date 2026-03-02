"""Convert SVG shape elements to equivalent <path> elements."""

import re
import math
from copy import deepcopy
from lxml import etree

SVG_NS = "http://www.w3.org/2000/svg"
SVGP = f"{{{SVG_NS}}}"

# Attributes to copy from source shape to new <path>
_COPY_ATTRS = {
    "id", "class", "style", "fill", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
    "stroke-dashoffset", "opacity", "fill-opacity", "stroke-opacity",
    "fill-rule", "clip-path", "mask", "visibility", "display",
    "transform",
}

# Shapes we know how to convert
_SHAPE_TAGS = {"rect", "circle", "ellipse", "line", "polygon", "polyline"}


def _f(v: float, decimals: int = 4) -> str:
    """Format float, removing trailing zeros."""
    s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-") else "0"


def _parse_points(s: str) -> list[tuple[float, float]]:
    """Parse SVG points attribute into list of (x, y) tuples."""
    nums = [float(n) for n in re.split(r"[\s,]+", s.strip()) if n]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _get(el, attr: str, default: str = "0") -> float:
    return float(el.get(attr, default) or default)


# ── Shape conversion functions ────────────────────────────────────────────────

def _rect_to_d(el) -> str:
    x = _get(el, "x")
    y = _get(el, "y")
    w = _get(el, "width")
    h = _get(el, "height")
    rx = el.get("rx")
    ry = el.get("ry")

    if rx is None and ry is None:
        rx_f = ry_f = 0.0
    else:
        rx_f = float(rx) if rx is not None else 0.0
        ry_f = float(ry) if ry is not None else 0.0
        if rx is None:
            rx_f = ry_f
        if ry is None:
            ry_f = rx_f
        rx_f = min(rx_f, w / 2)
        ry_f = min(ry_f, h / 2)

    if rx_f == 0 and ry_f == 0:
        return (
            f"M {_f(x)},{_f(y)} "
            f"H {_f(x + w)} "
            f"V {_f(y + h)} "
            f"H {_f(x)} "
            f"Z"
        )
    else:
        # Rounded rectangle: 4 arcs, 4 straight edges
        r = f"{_f(rx_f)},{_f(ry_f)} 0 0 1"
        return (
            f"M {_f(x + rx_f)},{_f(y)} "
            f"H {_f(x + w - rx_f)} "
            f"A {r} {_f(x + w)},{_f(y + ry_f)} "
            f"V {_f(y + h - ry_f)} "
            f"A {r} {_f(x + w - rx_f)},{_f(y + h)} "
            f"H {_f(x + rx_f)} "
            f"A {r} {_f(x)},{_f(y + h - ry_f)} "
            f"V {_f(y + ry_f)} "
            f"A {r} {_f(x + rx_f)},{_f(y)} "
            f"Z"
        )


def _circle_to_d(el) -> str:
    cx = _get(el, "cx")
    cy = _get(el, "cy")
    r = _get(el, "r")
    # Two semicircles
    return (
        f"M {_f(cx + r)},{_f(cy)} "
        f"A {_f(r)},{_f(r)} 0 1 1 {_f(cx - r)},{_f(cy)} "
        f"A {_f(r)},{_f(r)} 0 1 1 {_f(cx + r)},{_f(cy)} "
        f"Z"
    )


def _ellipse_to_d(el) -> str:
    cx = _get(el, "cx")
    cy = _get(el, "cy")
    rx = _get(el, "rx")
    ry = _get(el, "ry")
    return (
        f"M {_f(cx + rx)},{_f(cy)} "
        f"A {_f(rx)},{_f(ry)} 0 1 1 {_f(cx - rx)},{_f(cy)} "
        f"A {_f(rx)},{_f(ry)} 0 1 1 {_f(cx + rx)},{_f(cy)} "
        f"Z"
    )


def _line_to_d(el) -> str:
    x1 = _get(el, "x1")
    y1 = _get(el, "y1")
    x2 = _get(el, "x2")
    y2 = _get(el, "y2")
    return f"M {_f(x1)},{_f(y1)} L {_f(x2)},{_f(y2)}"


def _polygon_to_d(el) -> str:
    pts = _parse_points(el.get("points", ""))
    if not pts:
        return ""
    parts = [f"M {_f(pts[0][0])},{_f(pts[0][1])}"]
    for x, y in pts[1:]:
        parts.append(f"L {_f(x)},{_f(y)}")
    parts.append("Z")
    return " ".join(parts)


def _polyline_to_d(el) -> str:
    pts = _parse_points(el.get("points", ""))
    if not pts:
        return ""
    parts = [f"M {_f(pts[0][0])},{_f(pts[0][1])}"]
    for x, y in pts[1:]:
        parts.append(f"L {_f(x)},{_f(y)}")
    return " ".join(parts)


_CONVERTERS = {
    "rect": _rect_to_d,
    "circle": _circle_to_d,
    "ellipse": _ellipse_to_d,
    "line": _line_to_d,
    "polygon": _polygon_to_d,
    "polyline": _polyline_to_d,
}


def _local_tag(el) -> str:
    """Strip namespace from tag name."""
    t = el.tag
    if isinstance(t, str) and "}" in t:
        return t.split("}", 1)[1]
    return t if isinstance(t, str) else ""


def _convert_element(el, parent) -> bool:
    """
    Replace a shape element with an equivalent <path> element in-place.
    Returns True if converted.
    """
    local = _local_tag(el)
    if local not in _CONVERTERS:
        return False

    d = _CONVERTERS[local](el)
    if not d:
        return False

    path_el = etree.Element(f"{SVGP}path")
    path_el.set("d", d)

    for attr in _COPY_ATTRS:
        val = el.get(attr)
        if val is not None:
            path_el.set(attr, val)

    # Preserve tail text (whitespace between elements)
    path_el.tail = el.tail

    idx = list(parent).index(el)
    parent.remove(el)
    parent.insert(idx, path_el)
    return True


def _skip_tag(local: str) -> bool:
    return local in {"defs", "symbol", "use", "text", "tspan", "image",
                     "script", "style", "title", "desc", "metadata"}


def _walk_and_convert(el):
    """Recursively convert all shape elements in the tree."""
    local = _local_tag(el)

    if _skip_tag(local):
        return

    children = list(el)
    for child in children:
        child_local = _local_tag(child)
        if child_local in _SHAPE_TAGS:
            _convert_element(child, el)
        elif not _skip_tag(child_local):
            _walk_and_convert(child)


def convert_all_shapes(svg_content: str) -> str:
    """
    Convert all SVG shape elements to <path> elements.
    Returns the modified SVG as a string.
    """
    parser = etree.XMLParser(remove_comments=True, recover=True)
    root = etree.fromstring(svg_content.encode(), parser)

    _walk_and_convert(root)

    return etree.tostring(root, encoding="unicode", xml_declaration=False)
