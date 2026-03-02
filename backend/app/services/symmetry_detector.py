"""
Symmetry axis detection via 1D projection + FFT self-convolution.

Mathematical foundation
-----------------------
For a candidate axis at angle θ (direction (cos θ, sin θ)), the signed distance
of each sample point from the axis is its projection onto the axis normal:

    s_i = -x_i·sin θ + y_i·cos θ

If the shape has bilateral symmetry around an axis at signed distance d from the
centroid, then h(d + δ) = h(d - δ) for all δ, i.e., the histogram h of {s_i} is
symmetric around d.

Key identity: the *self-convolution* (h★h)[k] = Σ_j h[j]·h[k-j] satisfies:

    max(h★h) = Σ h²,   achieved iff h is symmetric around k*/2

where k* = argmax(h★h).  Proof: by Cauchy-Schwarz, Σ_j h[j]·h[k-j] ≤ Σ h²,
with equality iff h[j] = h[k-j] for all j, i.e., h is symmetric around k/2.

Therefore:
    score(θ) = max(h★h) / Σ h²  ∈ [0, 1],   1 = perfect symmetry
    d         = s_lo + argmax(h★h) · Δs / 2

Algorithm
---------
1. Sample ~50 pts/segment from every <path>.
2. Coarse scan: 360 angles over [0°, 180°) at 0.5° resolution.
3. Fine scan: 200 angles in ±2° around the best coarse angle at 0.02° resolution.
4. Convert (θ, d) to SVG axis geometry.

No iterative optimizer is used — the score surface is evaluated on a dense grid,
which is fast (all numpy/FFT, typically < 200 ms) and has no local-minima risk.
"""

import math
import numpy as np
from lxml import etree
from svgpathtools import parse_path

SVG_NS = "http://www.w3.org/2000/svg"

_N_PER_SEG   = 64    # sample points per bezier/arc segment
_N_COARSE    = 360   # coarse sweep: 0.5° steps over [0°, 180°)
_N_FINE      = 200   # fine sweep: 0.02° steps over ±2° around best coarse
_FINE_RANGE  = 2.0   # ± degrees for fine sweep
_N_BINS      = 512   # histogram bins


# ── SVG helpers ───────────────────────────────────────────────────────────────

def _local_tag(el) -> str:
    t = el.tag
    if isinstance(t, str) and "}" in t:
        return t.split("}", 1)[1]
    return t if isinstance(t, str) else ""


def _collect_path_d(root) -> list[str]:
    return [
        el.get("d", "").strip()
        for el in root.iter()
        if _local_tag(el) == "path" and el.get("d", "").strip()
    ]


def _sample_path(d: str) -> np.ndarray:
    try:
        path = parse_path(d)
    except Exception:
        return np.empty((0, 2))

    pts: list[list[float]] = []
    for seg in path:
        try:
            seg_len = abs(seg.length())
        except Exception:
            seg_len = 50.0
        # Clamp samples: at least 2, at most 256, proportional to arc-length
        n = max(2, min(256, int(_N_PER_SEG * max(seg_len, 1.0) / 50.0)))
        for t in np.linspace(0.0, 1.0, n, endpoint=False):
            try:
                p = seg.point(t)
                pts.append([p.real, p.imag])
            except Exception:
                pass
    return np.array(pts) if pts else np.empty((0, 2))


# ── Core scoring ──────────────────────────────────────────────────────────────

def _score_angle(pts_c: np.ndarray, theta: float, n_bins: int = _N_BINS):
    """
    Return (score, d) for a candidate axis at angle theta.

    pts_c : (N, 2) centroid-centred sample points
    theta : axis direction angle in radians
    score : ∈ [0, 1], 1 = perfect bilateral symmetry
    d     : signed distance of axis from centroid along axis normal
    """
    # Project onto axis normal: n = (−sin θ, cos θ)
    s = -pts_c[:, 0] * math.sin(theta) + pts_c[:, 1] * math.cos(theta)

    s_lo = s.min()
    s_hi = s.max()
    span = s_hi - s_lo
    if span < 1e-12:
        return 1.0, 0.0  # degenerate: all points collinear → trivially "symmetric"

    # Small margin so extreme points aren't cut off
    margin = span * 0.05
    s_lo -= margin
    s_hi += margin
    bin_w = (s_hi - s_lo) / n_bins

    hist, _ = np.histogram(s, bins=n_bins, range=(s_lo, s_hi))
    hist = hist.astype(np.float64)

    sum_sq = float(np.dot(hist, hist))
    if sum_sq < 1e-12:
        return 0.0, 0.0

    # Self-convolution via FFT (zero-padded → linear, not circular, convolution)
    H  = np.fft.rfft(hist, n=2 * n_bins)
    CC = np.fft.irfft(H * H)          # length = 2 * n_bins

    # Peak lives in [0 … 2*(n_bins-1)]; skip the very first bin to avoid
    # the trivial DC artefact when all mass is at one edge.
    valid = CC[1 : 2 * n_bins - 1]
    peak_local = int(np.argmax(valid))
    peak_idx   = peak_local + 1        # index in CC
    peak_val   = float(CC[peak_idx])

    score = peak_val / sum_sq          # ∈ [0, 1]
    d     = s_lo + peak_idx * bin_w / 2.0

    return score, d


# ── Public API ────────────────────────────────────────────────────────────────

def detect_axis(svg_content: str, viewbox: list[float]) -> dict:
    """
    Detect the approximate bilateral symmetry axis of the SVG.

    Requires the SVG to already contain <path> elements (run convert-to-paths
    before calling this).

    Returns a dict with:
        angle_deg   – axis direction in degrees [0, 180)
        cx, cy      – a point on the axis (in SVG user units)
        score       – asymmetry score ∈ [0, 1], 0 = perfect symmetry
        axis_p1/p2  – two far endpoints for visualization
    """
    parser = etree.XMLParser(remove_comments=True, recover=True)
    root = etree.fromstring(svg_content.encode(), parser)

    d_attrs = _collect_path_d(root)
    if not d_attrs:
        raise ValueError("No <path> elements found. Convert shapes to paths first.")

    pts_list = [_sample_path(d) for d in d_attrs]
    all_pts  = np.vstack([p for p in pts_list if len(p) > 0])

    if len(all_pts) < 4:
        raise ValueError("Too few sample points; paths may be empty or degenerate.")

    centroid = all_pts.mean(axis=0)
    pts_c    = all_pts - centroid   # work in centroid-centred coordinates

    # ── Coarse sweep ──────────────────────────────────────────────────────────
    # [0, π) covers all unique axis orientations (θ and θ+π are the same axis)
    coarse_angles = np.linspace(0.0, math.pi, _N_COARSE, endpoint=False)

    best_score_coarse = -math.inf
    best_theta_coarse = coarse_angles[0]

    for theta in coarse_angles:
        score, _ = _score_angle(pts_c, theta)
        if score > best_score_coarse:
            best_score_coarse = score
            best_theta_coarse = theta

    # ── Fine sweep ────────────────────────────────────────────────────────────
    fine_lo = best_theta_coarse - math.radians(_FINE_RANGE)
    fine_hi = best_theta_coarse + math.radians(_FINE_RANGE)
    fine_angles = np.linspace(fine_lo, fine_hi, _N_FINE, endpoint=True)

    best_score = -math.inf
    best_theta = best_theta_coarse
    best_d     = 0.0

    for theta in fine_angles:
        score, d = _score_angle(pts_c, theta)
        if score > best_score:
            best_score = score
            best_theta = theta
            best_d     = d

    # Normalise angle to [0, π)
    best_theta = best_theta % math.pi

    # ── Convert to SVG coordinates ────────────────────────────────────────────
    n_vec    = np.array([-math.sin(best_theta), math.cos(best_theta)])
    axis_pt  = centroid + best_d * n_vec

    cx, cy    = float(axis_pt[0]), float(axis_pt[1])
    angle_deg = float(math.degrees(best_theta))

    vb_w = viewbox[2] if viewbox[2] > 0 else 500
    vb_h = viewbox[3] if viewbox[3] > 0 else 500
    vis_span = math.sqrt(vb_w ** 2 + vb_h ** 2) * 1.5
    u_vec = np.array([math.cos(best_theta), math.sin(best_theta)])
    p1 = axis_pt - vis_span * u_vec
    p2 = axis_pt + vis_span * u_vec

    # Reported score: 1 − symmetry_score so that 0 = perfect (consistent with
    # the old "lower is better" convention shown in the UI)
    reported_score = float(max(0.0, 1.0 - best_score))

    return {
        "angle_deg": angle_deg,
        "cx": cx,
        "cy": cy,
        "score": reported_score,
        "axis_p1": [float(p1[0]), float(p1[1])],
        "axis_p2": [float(p2[0]), float(p2[1])],
    }
