"""SVG upload, conversion, and width visualization endpoints."""

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field

from ..services.svg_parser import parse_svg
from ..services.path_converter import convert_all_shapes
from ..services.width_visualizer import add_width_overlay
from ..services.svg_cropper import crop_svg

router = APIRouter()


class SvgBody(BaseModel):
    svg_content: str


class WidthBody(BaseModel):
    svg_content: str
    width_mm: float = Field(default=6.0, gt=0)
    px_per_mm: float = Field(default=3.7795, gt=0)


class CropBody(BaseModel):
    svg_content: str
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


@router.post("/upload")
async def upload_svg(file: UploadFile = File(...)):
    """Upload an SVG file and return parsed metadata + sanitized SVG string."""
    if file.content_type not in ("image/svg+xml", "text/xml", "application/xml", "text/plain"):
        # Try to be lenient; some tools send wrong MIME
        if not (file.filename or "").lower().endswith(".svg"):
            raise HTTPException(400, "File must be an SVG.")

    content = await file.read()
    try:
        result = parse_svg(content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to parse SVG: {e}")

    return result


@router.post("/convert-to-paths")
async def convert_to_paths(body: SvgBody):
    """Replace all SVG shape elements with equivalent <path> elements."""
    try:
        converted = convert_all_shapes(body.svg_content)
    except Exception as e:
        raise HTTPException(500, f"Conversion failed: {e}")
    return {"svg_content": converted}


@router.post("/crop")
async def crop_svg_endpoint(body: CropBody):
    """Clip SVG to a rectangle and update the viewBox. Also converts shapes to paths."""
    try:
        result = crop_svg(body.svg_content, body.x, body.y, body.width, body.height)
    except Exception as e:
        raise HTTPException(500, f"Crop failed: {e}")
    return result


@router.post("/visualize-width")
async def visualize_width(body: WidthBody):
    """Add a CNC bit-width buffer overlay to the SVG."""
    try:
        result = add_width_overlay(body.svg_content, body.width_mm, body.px_per_mm)
    except Exception as e:
        raise HTTPException(500, f"Width visualization failed: {e}")
    return {"svg_content": result}
