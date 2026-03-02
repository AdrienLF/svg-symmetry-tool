"""
Crop an SVG to a rectangular region.

Steps:
1. Auto-convert all shape elements to <path> so every element is clippable.
2. Clip every <path> to the crop rectangle via Shapely.
3. Remove paths that become empty after clipping.
4. Update the viewBox (and width/height if in real units) to the crop bounds.
"""

import re
import numpy as np
from lxml import etree
from svgpathtools import parse_path
from shapely.geometry import LineString, Polygon, box as shapely_box
from shapely.ops import unary_union

from .path_converter import convert_all_shapes

SVG_NS = "http://www.w3.org/2000/svg"
SVGP = f"{{{SVG_NS}}}"

_SAMPLES_PER_UNIT = 2.0
_MIN_SAMPLES = 32


def _local_tag(el) -> str:
    t = el.tag
    if isinstance(t, str) and "}" in t:
        return t.split("}", 1)[1]
    return t if isinstance(t, str) else ""


def _is_closed(d: str) -> bool:
    return bool(re.search(r"[Zz]\s*$", d.strip()))


def _sample_path(d: str) -> list[tuple[float, float]]:
    try:
        path = parse_path(d)
    except Exception:
        return []
    pts: list[tuple[float, float]] = []
    for seg in path:
        try:
            seg_len = abs(seg.length())
        except Exception:
            seg_len = 50.0
        n = min(512, max(_MIN_SAMPLES, int(seg_len * _SAMPLES_PER_UNIT)))
        for t in np.linspace(0.0, 1.0, n, endpoint=True):
            try:
                p = seg.point(t)
                pts.append((p.real, p.imag))
            except Exception:
                pass
    return pts


def _to_shapely(d: str):
    pts = _sample_path(d)
    if len(pts) < 2:
        return None
    if _is_closed(d) and len(pts) >= 3:
        try:
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 0:
                return poly
        except Exception:
            pass
    return LineString(pts)


def _geom_to_d(geom) -> str:
    """Convert any Shapely geometry to SVG path d string."""
    parts: list[str] = []

    def _ring(coords, close: bool) -> str:
        pts = list(coords)
        if not pts:
            return ""
        s = f"M {pts[0][0]:.4f},{pts[0][1]:.4f}"
        for x, y in pts[1:]:
            s += f" L {x:.4f},{y:.4f}"
        if close:
            s += " Z"
        return s

    def _walk(g):
        if g is None or g.is_empty:
            return
        t = g.geom_type
        if t == "Polygon":
            d = _ring(g.exterior.coords, True)
            for interior in g.interiors:
                d += " " + _ring(interior.coords, True)
            if d:
                parts.append(d)
        elif t == "LineString":
            d = _ring(g.coords, False)
            if d:
                parts.append(d)
        elif t in ("MultiPolygon", "MultiLineString", "GeometryCollection"):
            for sub in g.geoms:
                _walk(sub)

    _walk(geom)
    return " ".join(parts)


# ── Unit helpers ──────────────────────────────────────────────────────────────

_UNIT_TO_PX = {
    "px": 1.0, "mm": 96 / 25.4, "cm": 96 / 2.54,
    "in": 96.0, "pt": 96 / 72.0, "pc": 96 * 12 / 72.0,
}


def _scale_attr(attr_val: str, scale: float) -> str:
    """Scale a dimensional attribute value (e.g. '200mm') by a factor."""
    if not attr_val or attr_val.endswith("%"):
        return attr_val
    m = re.match(r"^([+-]?[\d.]+(?:[eE][+-]?\d+)?)\s*([a-z]*)$", attr_val.strip(), re.I)
    if not m:
        return attr_val
    return f"{float(m.group(1)) * scale:.6g}{m.group(2)}"


# ── Public API ────────────────────────────────────────────────────────────────

def crop_svg(svg_content: str, x: float, y: float, width: float, height: float) -> dict:
    """
    Clip all SVG content to the rectangle [x, y, x+width, y+height].

    Returns:
        {"svg_content": str, "viewBox": [x, y, width, height]}
    """
    # 1. Convert all shapes → paths so every drawable element is clippable
    svg_content = convert_all_shapes(svg_content)

    parser = etree.XMLParser(remove_comments=True, recover=True)
    root = etree.fromstring(svg_content.encode(), parser)

    # Record original viewBox for proportional scaling of width/height attrs
    orig_vb_str = root.get("viewBox", "")
    orig_vb = [0.0, 0.0, 0.0, 0.0]
    if orig_vb_str:
        parts = re.split(r"[\s,]+", orig_vb_str.strip())
        if len(parts) == 4:
            orig_vb = [float(p) for p in parts]

    crop_box = shapely_box(x, y, x + width, y + height)

    # 2. Clip every <path> element
    to_remove: list[etree._Element] = []

    for el in root.iter():
        if _local_tag(el) != "path":
            continue
        d = el.get("d", "").strip()
        if not d:
            to_remove.append(el)
            continue

        geom = _to_shapely(d)
        if geom is None:
            to_remove.append(el)
            continue

        try:
            clipped = geom.intersection(crop_box)
        except Exception:
            to_remove.append(el)
            continue

        if clipped.is_empty:
            to_remove.append(el)
        else:
            new_d = _geom_to_d(clipped)
            if new_d:
                el.set("d", new_d)
            else:
                to_remove.append(el)

    for el in to_remove:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)

    # 3. Update viewBox
    root.set("viewBox", f"{x} {y} {width} {height}")

    # 4. Scale width / height attributes proportionally (preserves physical size)
    if orig_vb[2] > 0:
        w_scale = width / orig_vb[2]
        w_attr = root.get("width", "")
        if w_attr and not w_attr.endswith("%"):
            root.set("width", _scale_attr(w_attr, w_scale))

    if orig_vb[3] > 0:
        h_scale = height / orig_vb[3]
        h_attr = root.get("height", "")
        if h_attr and not h_attr.endswith("%"):
            root.set("height", _scale_attr(h_attr, h_scale))

    svg_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return {
        "svg_content": svg_str,
        "viewBox": [x, y, width, height],
    }
