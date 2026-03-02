"""SVG parsing, unit detection, and metadata extraction."""

import re
from lxml import etree

SVG_NS = "http://www.w3.org/2000/svg"

# Pixel equivalents at 96 dpi
_UNIT_TO_PX: dict[str, float] = {
    "px": 1.0,
    "mm": 96.0 / 25.4,
    "cm": 96.0 / 2.54,
    "in": 96.0,
    "pt": 96.0 / 72.0,
    "pc": 96.0 * 12.0 / 72.0,
}


def _parse_length(s: str) -> tuple[float, str]:
    """Return (value, unit) from a CSS length string like '210mm' or '595.28'."""
    s = s.strip()
    m = re.match(r"^([+-]?[\d.]+(?:[eE][+-]?\d+)?)\s*([a-z%]*)$", s, re.I)
    if not m:
        return 0.0, "px"
    value = float(m.group(1))
    unit = m.group(2).lower() or "px"
    return value, unit


def _length_to_px(s: str) -> float:
    value, unit = _parse_length(s)
    return value * _UNIT_TO_PX.get(unit, 1.0)


def parse_svg(content: bytes | str) -> dict:
    """
    Parse SVG content and return metadata + sanitized SVG string.

    Returns:
        svg_content: cleaned SVG string (width/height forced to 100% for display)
        viewBox: [min_x, min_y, width, height]
        unit: detected physical unit ('mm', 'cm', 'in', 'px')
        px_per_mm: how many SVG user-units correspond to 1 mm
    """
    if isinstance(content, str):
        content = content.encode()

    parser = etree.XMLParser(remove_comments=True, recover=True)
    tree = etree.fromstring(content, parser)

    # Handle both namespaced and plain SVG roots
    tag = tree.tag
    if not (tag == "svg" or tag == f"{{{SVG_NS}}}svg"):
        raise ValueError("Root element is not <svg>")

    width_attr = tree.get("width", "")
    height_attr = tree.get("height", "")
    viewbox_attr = tree.get("viewBox", "")

    # Determine viewBox
    viewbox: list[float] = [0, 0, 0, 0]
    if viewbox_attr:
        parts = re.split(r"[\s,]+", viewbox_attr.strip())
        if len(parts) == 4:
            viewbox = [float(p) for p in parts]

    # If no viewBox, create one from width/height
    if viewbox[2] == 0 and width_attr:
        w_px = _length_to_px(width_attr)
        h_px = _length_to_px(height_attr) if height_attr else w_px
        viewbox = [0, 0, w_px, h_px]
        tree.set("viewBox", f"0 0 {w_px} {h_px}")

    # Detect physical unit from width attribute
    detected_unit = "px"
    px_per_mm = _UNIT_TO_PX["mm"]  # default: px document

    if width_attr:
        _, unit = _parse_length(width_attr)
        if unit in _UNIT_TO_PX:
            detected_unit = unit
            w_value, _ = _parse_length(width_attr)
            w_px = w_value * _UNIT_TO_PX[unit]
            if viewbox[2] > 0 and w_px > 0:
                # SVG user units per mm = viewBox_width / (physical_width_in_mm)
                w_mm = w_px / _UNIT_TO_PX["mm"]
                px_per_mm = viewbox[2] / w_mm

    # For display: replace explicit width/height with 100% so it fills its container
    tree.set("width", "100%")
    tree.set("height", "100%")

    svg_string = etree.tostring(tree, encoding="unicode", xml_declaration=False)
    # Remove any xml-stylesheet PIs that could cause browser issues
    svg_string = re.sub(r"<\?xml[^?]*\?>", "", svg_string).strip()

    return {
        "svg_content": svg_string,
        "viewBox": viewbox,
        "unit": detected_unit,
        "px_per_mm": px_per_mm,
    }
