"""
Symmetry detection test suite — 10 cases of increasing difficulty.

Design rules
------------
* Single T-shapes / arrow shapes are used for tests 1-6 to guarantee a
  unique axis.  Rectangle and circle pairs are intentionally avoided because
  two identical mirrored rectangles yield score ≈ 1 at every angle (the
  histogram is symmetric for any projection direction), giving the algorithm
  no way to discriminate.
* Tests 7-9 use shape pairs that are not point-symmetric, ensuring a unique
  axis with a clear FFT score peak.
"""

import base64
import math

from lxml import etree

from .symmetry_detector import detect_axis

SVG_NS = "http://www.w3.org/2000/svg"
W, H   = 500, 500    # viewBox for every test
CX, CY = 250, 250    # viewBox centre


# ── Geometry helpers ───────────────────────────────────────────────────────────

def _reflect_point(x, y, ax, ay, angle_deg):
    """Reflect (x, y) across the axis through (ax, ay) at direction angle_deg."""
    theta = math.radians(angle_deg)
    c2 = math.cos(2 * theta)
    s2 = math.sin(2 * theta)
    dx, dy = x - ax, y - ay
    return ax + c2 * dx + s2 * dy, ay + s2 * dx - c2 * dy


def _rotate_point(x, y, angle_deg, cx=CX, cy=CY):
    """Rotate (x, y) around (cx, cy) by angle_deg (CCW positive)."""
    a  = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    dx, dy = x - cx, y - cy
    return round(cx + c*dx - s*dy, 2), round(cy + s*dx + c*dy, 2)


def _angle_error(a1, a2):
    """Minimum unsigned difference between two axis angles (mod 180°)."""
    d = abs(a1 - a2) % 180
    return min(d, 180 - d)


def _perpendicular_center_error(exp_cx, exp_cy, det_cx, det_cy, det_angle_deg):
    """
    Distance from the detected centre to the expected axis line,
    measured along the axis-normal direction.
    """
    theta = math.radians(det_angle_deg)
    nx, ny = -math.sin(theta), math.cos(theta)
    return abs((det_cx - exp_cx) * nx + (det_cy - exp_cy) * ny)


# ── SVG path string builders ───────────────────────────────────────────────────

def _polygon_path(*pts):
    """pts: iterable of (x, y) tuples → closed polygon path string."""
    coords = " L ".join(f"{round(x, 2)},{round(y, 2)}" for x, y in pts)
    return f"M {coords} Z"


def _cubic_bezier_path(sx, sy, cp1x, cp1y, cp2x, cp2y, ex, ey):
    return f"M {sx},{sy} C {cp1x},{cp1y} {cp2x},{cp2y} {ex},{ey}"


def _star_points(cx, cy, r_outer, r_inner, n=5):
    """Return alternating outer/inner vertex list for a regular star."""
    pts = []
    for k in range(2 * n):
        r = r_outer if k % 2 == 0 else r_inner
        angle = math.radians(-90 + k * 180 / n)
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def _svg_wrap(*path_d_list):
    paths = "\n  ".join(
        f'<path d="{d}" fill="none" stroke="black" stroke-width="2"/>'
        for d in path_d_list
    )
    return (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">\n  {paths}\n</svg>'
    )


# ── Axis overlay for thumbnails ────────────────────────────────────────────────

def _build_axis_overlay(svg_content: str, angle_deg: float, cx: float, cy: float) -> str:
    """Inject a red dashed axis line into the SVG for thumbnail display."""
    parser = etree.XMLParser(remove_comments=True, recover=True)
    root   = etree.fromstring(svg_content.encode(), parser)

    theta    = math.radians(angle_deg)
    ux, uy   = math.cos(theta), math.sin(theta)
    span     = math.sqrt(W ** 2 + H ** 2)
    x1, y1   = cx - span * ux, cy - span * uy
    x2, y2   = cx + span * ux, cy + span * uy

    line = etree.SubElement(root, f"{{{SVG_NS}}}line")
    line.set("x1", str(round(x1, 2))); line.set("y1", str(round(y1, 2)))
    line.set("x2", str(round(x2, 2))); line.set("y2", str(round(y2, 2)))
    line.set("stroke", "#f43f5e")
    line.set("stroke-width", "3")
    line.set("stroke-dasharray", "12 6")
    line.set("stroke-linecap", "round")

    return etree.tostring(root, encoding="unicode")


def _svg_to_data_uri(svg_content: str) -> str:
    b64 = base64.b64encode(svg_content.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"


# ── Predefined shapes ──────────────────────────────────────────────────────────

# Vertical T-shape centred at x=250 (bar at top, stem pointing down).
# NOT y-symmetric (bar heavy at top, stem long below) → unique vertical axis.
_T_VERT = [(100,80),(400,80),(400,130),(280,130),(280,420),(220,420),(220,130),(100,130)]

# Arrow pointing up, centred at x=250.
# Asymmetric in y → no spurious horizontal axis.
_ARROW_UP = [(250,50),(350,200),(300,200),(300,420),(200,420),(200,200),(150,200)]

# Horizontal T-shape centred at y=250 (bar on left, stem pointing right).
_T_HORIZ = [(80,100),(130,100),(130,220),(420,220),(420,280),(130,280),(130,400),(80,400)]

# Off-centre T-shape, axis at x=180.
_T_OFF = [(30,80),(330,80),(330,130),(205,130),(205,420),(155,420),(155,130),(30,130)]

# Non-degenerate trapezoid pair, perfect mirror over x=250.
_TRAP_L = [(80,100),(180,200),(180,380),(80,380)]
_TRAP_R = [(420,100),(320,200),(320,380),(420,380)]


# ── Test case definitions ──────────────────────────────────────────────────────

def _all_test_cases():
    cases = []

    # 1. Vertical T-shape — easy ─────────────────────────────────────────────
    cases.append({
        "id": 1,
        "label": "T-shape — vertical axis",
        "difficulty": "easy",
        "svg": _svg_wrap(_polygon_path(*_T_VERT)),
        "expected_angle": 90.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 1.0, "center_tolerance": 5.0,
        "valid_angles": None,
    })

    # 2. Arrow pointing up — easy ─────────────────────────────────────────────
    cases.append({
        "id": 2,
        "label": "Arrow-up — vertical axis",
        "difficulty": "easy",
        "svg": _svg_wrap(_polygon_path(*_ARROW_UP)),
        "expected_angle": 90.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 1.0, "center_tolerance": 5.0,
        "valid_angles": None,
    })

    # 3. Horizontal T-shape — easy ────────────────────────────────────────────
    cases.append({
        "id": 3,
        "label": "T-shape — horizontal axis",
        "difficulty": "easy",
        "svg": _svg_wrap(_polygon_path(*_T_HORIZ)),
        "expected_angle": 0.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 1.0, "center_tolerance": 5.0,
        "valid_angles": None,
    })

    # 4. Off-centre vertical axis at x=180 — medium ──────────────────────────
    cases.append({
        "id": 4,
        "label": "T-shape — off-centre axis (x=180)",
        "difficulty": "medium",
        "svg": _svg_wrap(_polygon_path(*_T_OFF)),
        "expected_angle": 90.0, "expected_cx": 180.0, "expected_cy": 250.0,
        "angle_tolerance": 1.5, "center_tolerance": 8.0,
        "valid_angles": None,
    })

    # 5. Near-symmetric trapezoid pair (5 px shift) — medium ─────────────────
    trap_r5 = [(x + 5, y) for x, y in _TRAP_R]   # shift right trapezoid 5 px right
    cases.append({
        "id": 5,
        "label": "Trapezoid pair — 5 px asymmetry",
        "difficulty": "medium",
        "svg": _svg_wrap(_polygon_path(*_TRAP_L), _polygon_path(*trap_r5)),
        "expected_angle": 90.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 3.0, "center_tolerance": 20.0,
        "valid_angles": None,
    })

    # 6. T-shape rotated to 45° diagonal axis — medium ───────────────────────
    T45 = [_rotate_point(x, y, -45) for x, y in _T_VERT]
    cases.append({
        "id": 6,
        "label": "T-shape — 45° diagonal axis",
        "difficulty": "medium",
        "svg": _svg_wrap(_polygon_path(*T45)),
        "expected_angle": 45.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 2.0, "center_tolerance": 10.0,
        "valid_angles": None,
    })

    # 7. 30° diagonal axis — triangle pair — hard ────────────────────────────
    orig_7 = [(200, 150), (300, 150), (250, 100)]
    refl_7 = [_reflect_point(x, y, CX, CY, 30.0) for x, y in orig_7]
    cases.append({
        "id": 7,
        "label": "Triangle pair — 30° diagonal axis",
        "difficulty": "hard",
        "svg": _svg_wrap(_polygon_path(*orig_7), _polygon_path(*refl_7)),
        "expected_angle": 30.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 2.0, "center_tolerance": 15.0,
        "valid_angles": None,
    })

    # 8. Symmetric cubic bezier curves — vertical axis — hard ────────────────
    cases.append({
        "id": 8,
        "label": "Cubic beziers — vertical axis",
        "difficulty": "hard",
        "svg": _svg_wrap(
            _cubic_bezier_path(200, 150, 150, 100, 100, 200, 150, 300),
            _cubic_bezier_path(300, 150, 350, 100, 400, 200, 350, 300),
        ),
        "expected_angle": 90.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 2.0, "center_tolerance": 15.0,
        "valid_angles": None,
    })

    # 9. 5-pointed star — 5 valid axes — hard ────────────────────────────────
    star_pts = _star_points(CX, CY, 150, 60, 5)
    cases.append({
        "id": 9,
        "label": "5-pointed star — 5 valid axes",
        "difficulty": "hard",
        "svg": _svg_wrap(_polygon_path(*star_pts)),
        "expected_angle": 90.0, "expected_cx": CX, "expected_cy": CY,
        "angle_tolerance": 2.0, "center_tolerance": 10.0,
        "valid_angles": [18.0, 54.0, 90.0, 126.0, 162.0],
    })

    # 10. Trapezoid pair — 1.5 px asymmetry — very_hard ──────────────────────
    trap_r15 = [(x + 1.5, y) for x, y in _TRAP_R]
    cases.append({
        "id": 10,
        "label": "Trapezoid pair — 1.5 px asymmetry",
        "difficulty": "very_hard",
        "svg": _svg_wrap(_polygon_path(*_TRAP_L), _polygon_path(*trap_r15)),
        "expected_angle": 90.0, "expected_cx": 250.0, "expected_cy": 250.0,
        "angle_tolerance": 5.0, "center_tolerance": 25.0,
        "valid_angles": None,
    })

    return cases


# ── Public runner ──────────────────────────────────────────────────────────────

def run_all_tests() -> list[dict]:
    """
    Run all symmetry detection tests and return a list of result dicts.

    Each dict contains:
        id, label, difficulty, passed, error,
        svg_thumbnail (data URI with detected-axis overlay),
        expected_angle, expected_cx, expected_cy,
        detected_angle, detected_cx, detected_cy,
        angle_error, center_error, angle_tolerance, center_tolerance,
        score, valid_angles
    """
    results = []

    for case in _all_test_cases():
        det_angle = det_cx = det_cy = score = None
        ang_err = ctr_err = None
        passed   = False
        error_msg = None

        try:
            detection = detect_axis(case["svg"], [0, 0, W, H])
            det_angle = detection["angle_deg"]
            det_cx    = detection["cx"]
            det_cy    = detection["cy"]
            score     = detection["score"]

            ang_err = _angle_error(det_angle, case["expected_angle"])
            if case["valid_angles"]:
                ang_err = min(
                    _angle_error(det_angle, va) for va in case["valid_angles"]
                )

            ctr_err = _perpendicular_center_error(
                case["expected_cx"], case["expected_cy"],
                det_cx, det_cy, det_angle,
            )

            passed = (
                ang_err <= case["angle_tolerance"] and
                ctr_err <= case["center_tolerance"]
            )

        except Exception as e:
            error_msg = str(e)

        # Build thumbnail with detected axis (fall back to expected on error)
        vis_angle = det_angle if det_angle is not None else case["expected_angle"]
        vis_cx    = det_cx    if det_cx    is not None else case["expected_cx"]
        vis_cy    = det_cy    if det_cy    is not None else case["expected_cy"]
        try:
            thumb_svg = _build_axis_overlay(case["svg"], vis_angle, vis_cx, vis_cy)
        except Exception:
            thumb_svg = case["svg"]
        thumbnail = _svg_to_data_uri(thumb_svg)

        results.append({
            "id":               case["id"],
            "label":            case["label"],
            "difficulty":       case["difficulty"],
            "passed":           passed,
            "error":            error_msg,
            "svg_thumbnail":    thumbnail,
            "expected_angle":   case["expected_angle"],
            "expected_cx":      case["expected_cx"],
            "expected_cy":      case["expected_cy"],
            "detected_angle":   det_angle,
            "detected_cx":      det_cx,
            "detected_cy":      det_cy,
            "angle_error":      ang_err,
            "center_error":     ctr_err,
            "angle_tolerance":  case["angle_tolerance"],
            "center_tolerance": case["center_tolerance"],
            "score":            score,
            "valid_angles":     case["valid_angles"],
        })

    return results
