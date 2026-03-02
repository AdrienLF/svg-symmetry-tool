"""Symmetry detection and fixing endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.symmetry_detector import detect_axis
from ..services.symmetry_fixer import fix_symmetry
from ..services.symmetry_tests import run_all_tests

router = APIRouter()


class DetectBody(BaseModel):
    svg_content: str
    px_per_mm: float = Field(default=3.7795, gt=0)
    viewbox: list[float] = Field(default=[0, 0, 500, 500])


class FixBody(BaseModel):
    svg_content: str
    angle_deg: float
    cx: float
    cy: float
    keep_side: str = "positive"   # 'positive' | 'negative'


@router.post("/detect")
async def detect_symmetry(body: DetectBody):
    """
    Detect the approximate axis of symmetry in the SVG.
    Requires the SVG to have <path> elements (run convert-to-paths first).
    """
    try:
        result = detect_axis(body.svg_content, body.viewbox)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Symmetry detection failed: {e}")
    return result


@router.post("/fix")
async def fix_symmetry_endpoint(body: FixBody):
    """Mirror the chosen half of the SVG over the detected axis."""
    if body.keep_side not in ("positive", "negative"):
        raise HTTPException(400, "keep_side must be 'positive' or 'negative'")
    try:
        result = fix_symmetry(
            body.svg_content,
            body.angle_deg,
            body.cx,
            body.cy,
            body.keep_side,
        )
    except Exception as e:
        raise HTTPException(500, f"Symmetry fix failed: {e}")
    return {"svg_content": result}


@router.get("/tests")
async def symmetry_tests():
    """Run the built-in symmetry detection test suite and return results."""
    try:
        return {"results": run_all_tests()}
    except Exception as e:
        raise HTTPException(500, f"Test suite failed: {e}")
