"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import svg, symmetry

app = FastAPI(
    title="SVG Tools API",
    description="SVG visualization, path conversion, symmetry detection and fixing",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(svg.router, prefix="/api/svg", tags=["SVG"])
app.include_router(symmetry.router, prefix="/api/symmetry", tags=["Symmetry"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
