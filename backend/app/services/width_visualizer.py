"""
CNC bit-width visualization overlay.

For each <path> in the SVG, buffer it by half the bit diameter (in SVG user-units)
using Shapely to produce the area that would be removed by the router bit.
The result is a semi-transparent overlay group added to the SVG.
"""

import math
import numpy as np
from lxml import etree
from svgpathtools import parse_path
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

SVG_NS = "http://www.w3.org/2000/svg"
SVGP = f"{{{SVG_NS}}}"

_SAMPLES_PER_UNIT = 1.5
_MIN_SAMPLES = 32


def _local_tag(el) -> str:
    t = el.tag
    if isinstance(t, str) and "}" in t:
        return t.split("}", 1)[1]
    return t if isinstance(t, str) else ""


def _sample_path_to_linestring(d: str) -> LineString | None:
    try:
        path = parse_path(d)
    except Exception:
        return None

    pts: list[tuple[float, float]] = []
    for seg in path:
        try:
            seg_len = abs(seg.length())
        except Exception:
            seg_len = 50.0
        n = max(_MIN_SAMPLES, int(seg_len * _SAMPLES_PER_UNIT))
        n = min(n, 512)
        for t in np.linspace(0.0, 1.0, n, endpoint=True):
            try:
                p = seg.point(t)
                pts.append((p.real, p.imag))
            except Exception:
                pass

    if len(pts) < 2:
        return None
    return LineString(pts)


def _poly_to_d(poly: Polygon) -> str:
    """Convert a Shapely Polygon to an SVG path d string."""
    if poly.is_empty:
        return ""

    def _ring(coords) -> str:
        pts = list(coords)
        if not pts:
            return ""
        parts = [f"M {pts[0][0]:.3f},{pts[0][1]:.3f}"]
        for x, y in pts[1:]:
            parts.append(f"L {x:.3f},{y:.3f}")
        parts.append("Z")
        return " ".join(parts)

    d = _ring(poly.exterior.coords)
    for interior in poly.interiors:
        d += " " + _ring(interior.coords)
    return d


def _geometry_to_d(geom) -> str:
    """Convert any Shapely geometry to an SVG path d string."""
    parts: list[str] = []

    def _walk(g):
        if g is None or g.is_empty:
            return
        gtype = g.geom_type
        if gtype == "Polygon":
            d = _poly_to_d(g)
            if d:
                parts.append(d)
        elif gtype in ("MultiPolygon", "GeometryCollection"):
            for sub in g.geoms:
                _walk(sub)

    _walk(geom)
    return " ".join(parts)


def add_width_overlay(svg_content: str, width_mm: float, px_per_mm: float) -> str:
    """
    Add a semi-transparent buffer overlay representing the CNC bit width.

    Args:
        svg_content: SVG string (ideally all paths)
        width_mm: full bit diameter in mm
        px_per_mm: SVG user-units per mm

    Returns:
        Modified SVG string with an additional overlay <g> element.
    """
    half_radius_px = (width_mm / 2.0) * px_per_mm

    parser = etree.XMLParser(remove_comments=True, recover=True)
    root = etree.fromstring(svg_content.encode(), parser)

    # Remove any existing width overlay
    for el in root.iter():
        if el.get("id") == "width-overlay":
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
            break

    buffered_geoms = []
    for el in root.iter():
        if _local_tag(el) != "path":
            continue
        d = el.get("d", "").strip()
        if not d:
            continue

        ls = _sample_path_to_linestring(d)
        if ls is None:
            continue

        try:
            buffered = ls.buffer(
                half_radius_px,
                cap_style=1,    # round caps
                join_style=1,   # round joins
                resolution=16,
            )
            buffered_geoms.append(buffered)
        except Exception:
            pass

    if not buffered_geoms:
        return svg_content

    try:
        merged = unary_union(buffered_geoms)
    except Exception:
        merged = buffered_geoms[0]

    d_str = _geometry_to_d(merged)
    if not d_str:
        return svg_content

    # Build the overlay group
    overlay_g = etree.SubElement(root, f"{SVGP}g")
    overlay_g.set("id", "width-overlay")
    overlay_g.set("opacity", "0.35")
    overlay_g.set("fill", "#FF6B35")
    overlay_g.set("stroke", "none")
    overlay_g.set("pointer-events", "none")

    path_el = etree.SubElement(overlay_g, f"{SVGP}path")
    path_el.set("d", d_str)
    path_el.set("fill-rule", "evenodd")

    return etree.tostring(root, encoding="unicode", xml_declaration=False)
