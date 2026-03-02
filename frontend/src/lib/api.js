const BASE = '/api';

async function post(url, data) {
  const res = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export async function uploadSvg(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/svg/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export function cropSvg(svgContent, x, y, width, height) {
  return post('/svg/crop', { svg_content: svgContent, x, y, width, height });
}

export function convertToPaths(svgContent) {
  return post('/svg/convert-to-paths', { svg_content: svgContent });
}

export function visualizeWidth(svgContent, widthMm, pxPerMm) {
  return post('/svg/visualize-width', {
    svg_content: svgContent,
    width_mm: widthMm,
    px_per_mm: pxPerMm,
  });
}

export function detectSymmetry(svgContent, pxPerMm, viewbox) {
  return post('/symmetry/detect', {
    svg_content: svgContent,
    px_per_mm: pxPerMm,
    viewbox,
  });
}

export function fixSymmetry(svgContent, angleDeg, cx, cy, keepSide) {
  return post('/symmetry/fix', {
    svg_content: svgContent,
    angle_deg: angleDeg,
    cx,
    cy,
    keep_side: keepSide,
  });
}

export async function runSymmetryTests() {
  const res = await fetch(`${BASE}/symmetry/tests`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Tests failed');
  }
  return res.json();
}
