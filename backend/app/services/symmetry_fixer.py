"""
Fix symmetry by mirroring the chosen half over the detected axis.

Strategy
--------
For each <path> element:

  1.  Determine which side of the axis the path lies on (by sampling a few
      points):
        – entirely on the **kept** side  → keep it verbatim AND append its
          exact mirror (reflected control-point coordinates, no re-sampling)
        – entirely on the **opposite** side → discard it
        – **crossing** the axis → use Shapely to clip, reflect, and union
          (polyline approximation at ~2 pts/unit)

  Using exact reflection for non-crossing paths preserves bezier quality.
  The Shapely path is only used when a path must actually be split.
"""

import math
import re

import numpy as np
from lxml import etree
from shapely.affinity import affine_transform, translate
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import unary_union
from svgpathtools import Arc, CubicBezier, Line, Path, QuadraticBezier, parse_path

SVG_NS = "http://www.w3.org/2000/svg"
SVGP   = f"{{{SVG_NS}}}"

_SAMPLES_PER_UNIT = 2.0   # pts per SVG unit for Shapely approximation
_MIN_SAMPLES      = 32
_SIDE_PROBE_N     = 16    # points sampled to determine which side a path is on


# ── Axis helpers ───────────────────────────────────────────────────────────────

def _local_tag(el) -> str:
    t = el.tag
    if isinstance(t, str) and "}" in t:
        return t.split("}", 1)[1]
    return t if isinstance(t, str) else ""


def _signed_distance(x: float, y: float, cx: float, cy: float, theta: float) -> float:
    """
    Signed distance of (x,y) from the axis (positive = normal direction).
    normal = (-sin θ, cos θ)
    """
    return -(x - cx) * math.sin(theta) + (y - cy) * math.cos(theta)


def _path_side(d: str, cx: float, cy: float, theta: float) -> str:
    """
    Sample _SIDE_PROBE_N points from the path and classify as:
      'positive', 'negative', or 'crossing'
    """
    try:
        path = parse_path(d)
    except Exception:
        return "crossing"

    ts = np.linspace(0, 1, _SIDE_PROBE_N, endpoint=False)
    signs = set()
    for seg in path:
        for t in ts:
            try:
                p = seg.point(t)
                sd = _signed_distance(p.real, p.imag, cx, cy, theta)
                signs.add("positive" if sd > 1e-3 else "negative" if sd < -1e-3 else "zero")
            except Exception:
                pass

    signs.discard("zero")
    if not signs:
        return "zero"
    if len(signs) == 1:
        return signs.pop()
    return "crossing"


# ── Exact reflection on bezier paths ──────────────────────────────────────────

def _refl_complex(z: complex, cx: float, cy: float, c2: float, s2: float) -> complex:
    dx, dy = z.real - cx, z.imag - cy
    return complex(cx + c2 * dx + s2 * dy, cy + s2 * dx - c2 * dy)


def _reflect_d_exact(d: str, cx: float, cy: float, theta: float) -> str:
    """
    Reflect an SVG path d string across the axis — preserving bezier curves
    exactly (no sampling).  Returns a new d string.
    """
    try:
        path = parse_path(d)
    except Exception:
        return ""

    c2 = math.cos(2 * theta)
    s2 = math.sin(2 * theta)

    def R(z):
        return _refl_complex(z, cx, cy, c2, s2)

    segs = []
    for seg in path:
        if isinstance(seg, Line):
            segs.append(Line(R(seg.start), R(seg.end)))
        elif isinstance(seg, CubicBezier):
            segs.append(CubicBezier(R(seg.start), R(seg.control1),
                                    R(seg.control2), R(seg.end)))
        elif isinstance(seg, QuadraticBezier):
            segs.append(QuadraticBezier(R(seg.start), R(seg.control), R(seg.end)))
        elif isinstance(seg, Arc):
            # Reflection reverses the sweep direction
            segs.append(Arc(R(seg.start), seg.radius, -seg.rotation,
                            seg.arc, not seg.sweep, R(seg.end)))
        else:
            segs.append(seg)

    return Path(*segs).d() if segs else ""


# ── Shapely helpers (for crossing paths) ──────────────────────────────────────

def _sample_path_dense(d: str) -> list[tuple[float, float]]:
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


def _is_closed_path(d: str) -> bool:
    return bool(re.search(r"[Zz]\s*$", d.strip()))


def _path_to_shapely(d: str):
    pts = _sample_path_dense(d)
    if len(pts) < 2:
        return None
    if _is_closed_path(d) and len(pts) >= 3:
        try:
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 0:
                return poly
        except Exception:
            pass
    return LineString(pts)


def _make_halfplane(cx: float, cy: float, theta: float, side: str, size: float = 1e6):
    """Half-plane polygon on the given side of the axis."""
    n   = np.array([-math.sin(theta), math.cos(theta)])
    u   = np.array([math.cos(theta),  math.sin(theta)])
    O   = np.array([cx, cy])
    sgn = 1.0 if side == "positive" else -1.0
    corners = [
        O - size * u,
        O + size * u,
        O + size * u + sgn * size * n,
        O - size * u + sgn * size * n,
    ]
    return Polygon(corners)


def _reflect_shapely(geom, cx: float, cy: float, theta: float):
    geom_t = translate(geom, -cx, -cy)
    c2 = math.cos(2 * theta)
    s2 = math.sin(2 * theta)
    geom_r = affine_transform(geom_t, [c2, s2, s2, -c2, 0.0, 0.0])
    return translate(geom_r, cx, cy)


def _geometry_to_d(geom) -> list[str]:
    ds: list[str] = []

    def _ring_to_d(coords, close: bool) -> str:
        pts = list(coords)
        if not pts:
            return ""
        parts = [f"M {pts[0][0]:.4f},{pts[0][1]:.4f}"]
        for x, y in pts[1:]:
            parts.append(f"L {x:.4f},{y:.4f}")
        if close:
            parts.append("Z")
        return " ".join(parts)

    def _process(g):
        if g is None or g.is_empty:
            return
        gt = g.geom_type
        if gt == "Polygon":
            d = _ring_to_d(g.exterior.coords, close=True)
            for interior in g.interiors:
                d += " " + _ring_to_d(interior.coords, close=True)
            if d:
                ds.append(d)
        elif gt == "LineString":
            d = _ring_to_d(g.coords, close=False)
            if d:
                ds.append(d)
        elif gt in ("MultiPolygon", "MultiLineString", "GeometryCollection"):
            for sub in g.geoms:
                _process(sub)

    _process(geom)
    return ds


# ── Style helpers ──────────────────────────────────────────────────────────────

_STYLE_ATTRS = {
    "style", "fill", "stroke", "stroke-width", "stroke-linecap",
    "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity",
    "fill-rule", "class",
}


def _get_style(el) -> dict[str, str]:
    return {a: el.get(a) for a in _STYLE_ATTRS if el.get(a) is not None}


def _make_path_el(d: str, style: dict[str, str]) -> "etree._Element":
    el = etree.Element(f"{SVGP}path")
    el.set("d", d)
    for attr, val in style.items():
        el.set(attr, val)
    return el


# ── Public API ────────────────────────────────────────────────────────────────

def fix_symmetry(
    svg_content: str,
    angle_deg:   float,
    cx:          float,
    cy:          float,
    keep_side:   str,          # 'positive' | 'negative'
) -> str:
    """
    Mirror the chosen half of the SVG over the axis to create a perfectly
    symmetric design.

    keep_side='positive': keep the half in the direction of axis normal (-sinθ, cosθ)
    keep_side='negative': keep the opposite half
    """
    theta = math.radians(angle_deg)
    opp   = "negative" if keep_side == "positive" else "positive"

    parser = etree.XMLParser(remove_comments=True, recover=True)
    root   = etree.fromstring(svg_content.encode(), parser)

    halfplane = _make_halfplane(cx, cy, theta, keep_side)

    # Snapshot: collect (element, parent) before we mutate the tree
    snapshot = [
        (el, el.getparent())
        for el in list(root.iter())
        if _local_tag(el) == "path" and el.get("d", "").strip()
    ]

    for el, parent in snapshot:
        if parent is None:
            continue

        d     = el.get("d", "").strip()
        style = _get_style(el)
        side  = _path_side(d, cx, cy, theta)

        # ── Path is entirely on the opposite side → discard ───────────────
        if side == opp:
            parent.remove(el)
            continue

        # ── Path is entirely on the kept side → keep verbatim + add mirror ──
        if side in (keep_side, "zero"):
            mirror_d = _reflect_d_exact(d, cx, cy, theta)
            if mirror_d:
                idx = list(parent).index(el)
                mirror_el = _make_path_el(mirror_d, style)
                mirror_el.tail = el.tail
                parent.insert(idx + 1, mirror_el)
            # Original path stays untouched
            continue

        # ── Path crosses the axis → Shapely clip + reflect + union ────────
        geom = _path_to_shapely(d)
        if geom is None or geom.is_empty:
            parent.remove(el)
            continue

        try:
            kept = geom.intersection(halfplane)
        except Exception:
            kept = geom

        if kept.is_empty:
            parent.remove(el)
            continue

        reflected = _reflect_shapely(kept, cx, cy, theta)

        try:
            combined = unary_union([kept, reflected])
        except Exception:
            combined = kept

        d_strings = _geometry_to_d(combined)

        idx = list(parent).index(el)
        tail = el.tail
        parent.remove(el)

        for i, new_d in enumerate(d_strings):
            new_el = _make_path_el(new_d, style)
            if i == 0:
                new_el.tail = tail
            parent.insert(idx + i, new_el)

    return etree.tostring(root, encoding="unicode", xml_declaration=False)
