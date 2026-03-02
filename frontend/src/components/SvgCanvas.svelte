<script>
  import { createEventDispatcher } from 'svelte';

  export let svgContent = '';
  export let axis = null;         // null | { angle_deg, cx, cy, axis_p1, axis_p2, score }
  export let viewBox = [0, 0, 500, 500]; // [minX, minY, w, h]
  export let cropMode = false;
  export let cropRect = null;     // { x, y, w, h } in SVG user coords — bindable

  const dispatch = createEventDispatcher();

  let overlayEl;
  let dragging = null; // { handle: 'tl'|'tr'|'bl'|'br'|'move', startPt, startRect }

  $: vbStr = viewBox.join(' ');
  $: axisPts = axis
    ? { x1: axis.axis_p1[0], y1: axis.axis_p1[1], x2: axis.axis_p2[0], y2: axis.axis_p2[1] }
    : null;

  // Crop UI dimensions scaled to viewBox so handles look right at any SVG size
  $: vbMin = Math.min(viewBox[2], viewBox[3]);
  $: handleR = Math.max(2, vbMin * 0.018);
  $: strokeW = Math.max(0.3, vbMin * 0.003);
  $: dashLen = handleR * 2.2;

  // Dim overlay path: large outer rect with crop rect "hole" (evenodd fill)
  $: dimPath = (() => {
    if (!cropMode || !cropRect) return '';
    const margin = Math.max(viewBox[2], viewBox[3]) * 3;
    const ox = viewBox[0] - margin, oy = viewBox[1] - margin;
    const ow = viewBox[2] + margin * 2, oh = viewBox[3] + margin * 2;
    const { x, y, w, h } = cropRect;
    return (
      `M ${ox},${oy} H ${ox + ow} V ${oy + oh} H ${ox} Z ` +
      `M ${x},${y} H ${x + w} V ${y + h} H ${x} Z`
    );
  })();

  // Corner handle positions
  $: handles = cropMode && cropRect
    ? [
        { id: 'tl', cx: cropRect.x,            cy: cropRect.y,            cursor: 'nwse-resize' },
        { id: 'tr', cx: cropRect.x + cropRect.w, cy: cropRect.y,          cursor: 'nesw-resize' },
        { id: 'bl', cx: cropRect.x,            cy: cropRect.y + cropRect.h, cursor: 'nesw-resize' },
        { id: 'br', cx: cropRect.x + cropRect.w, cy: cropRect.y + cropRect.h, cursor: 'nwse-resize' },
      ]
    : [];

  // ── Coordinate conversion ──────────────────────────────────────────────────
  function toSvgPt(e) {
    if (!overlayEl) return { x: 0, y: 0 };
    const pt = overlayEl.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const m = overlayEl.getScreenCTM();
    if (!m) return { x: 0, y: 0 };
    const tp = pt.matrixTransform(m.inverse());
    return { x: tp.x, y: tp.y };
  }

  // ── Drag handlers ──────────────────────────────────────────────────────────
  function startDrag(e, handle) {
    if (!cropMode || !cropRect) return;
    e.preventDefault();
    e.stopPropagation();
    dragging = { handle, startPt: toSvgPt(e), startRect: { ...cropRect } };
  }

  function onMousemove(e) {
    if (!cropMode || !dragging || !cropRect) return;
    const pt = toSvgPt(e);
    const dx = pt.x - dragging.startPt.x;
    const dy = pt.y - dragging.startPt.y;
    const sr = dragging.startRect;
    const MIN = handleR * 3;

    let nx = sr.x, ny = sr.y, nw = sr.w, nh = sr.h;

    if (dragging.handle === 'move') {
      nx = sr.x + dx;
      ny = sr.y + dy;
    } else {
      if (dragging.handle.includes('l')) { nx = sr.x + dx; nw = Math.max(MIN, sr.w - dx); }
      if (dragging.handle.includes('r')) { nw = Math.max(MIN, sr.w + dx); }
      if (dragging.handle.includes('t')) { ny = sr.y + dy; nh = Math.max(MIN, sr.h - dy); }
      if (dragging.handle.includes('b')) { nh = Math.max(MIN, sr.h + dy); }
    }

    cropRect = { x: nx, y: ny, w: nw, h: nh };
  }

  function stopDrag() {
    dragging = null;
  }

  // Cursor for the whole overlay based on what's being dragged
  $: overlayCursor = (() => {
    if (!cropMode) return 'default';
    if (!dragging) return 'default';
    const h = dragging.handle;
    if (h === 'move') return 'move';
    if (h === 'tl' || h === 'br') return 'nwse-resize';
    return 'nesw-resize';
  })();
</script>

<div class="canvas-wrapper">
  <!-- SVG content rendered inline -->
  <div class="svg-host" aria-label="SVG preview">
    {@html svgContent}
  </div>

  <!-- Overlay SVG: always present; receives pointer events only in crop mode -->
  <svg
    class="overlay"
    class:interactive={cropMode}
    style="cursor: {overlayCursor};"
    viewBox={vbStr}
    xmlns="http://www.w3.org/2000/svg"
    preserveAspectRatio="xMidYMid meet"
    bind:this={overlayEl}
    on:mousemove={onMousemove}
    on:mouseup={stopDrag}
    on:mouseleave={stopDrag}
    aria-hidden="true"
  >
    <!-- ── Axis overlay (when not in crop mode) ───────────────────────── -->
    {#if axisPts && !cropMode}
      <line
        x1={axisPts.x1} y1={axisPts.y1}
        x2={axisPts.x2} y2={axisPts.y2}
        stroke="#f43f5e"
        stroke-width={strokeW * 2}
        stroke-dasharray="{dashLen * 2} {dashLen}"
        stroke-linecap="round"
      />
      <circle cx={axis.cx} cy={axis.cy} r={handleR * 0.8} fill="#f43f5e" opacity="0.9" />
      <text
        x={axis.cx + handleR * 1.2} y={axis.cy - handleR * 1.2}
        fill="#f43f5e"
        font-size={handleR * 1.8}
        font-family="monospace"
      >{axis.angle_deg.toFixed(1)}°</text>
    {/if}

    <!-- ── Crop overlay ───────────────────────────────────────────────── -->
    {#if cropMode && cropRect}
      <!-- Dark vignette outside crop region -->
      <path
        d={dimPath}
        fill="rgba(0,0,0,0.52)"
        fill-rule="evenodd"
        pointer-events="none"
      />

      <!-- Crop border -->
      <rect
        x={cropRect.x} y={cropRect.y}
        width={cropRect.w} height={cropRect.h}
        fill="none"
        stroke="white"
        stroke-width={strokeW}
        stroke-dasharray="{dashLen} {dashLen * 0.5}"
        pointer-events="none"
      />

      <!-- Rule-of-thirds grid lines inside crop area -->
      {#each [1/3, 2/3] as t}
        <line
          x1={cropRect.x + cropRect.w * t} y1={cropRect.y}
          x2={cropRect.x + cropRect.w * t} y2={cropRect.y + cropRect.h}
          stroke="rgba(255,255,255,0.2)" stroke-width={strokeW * 0.7}
          pointer-events="none"
        />
        <line
          x1={cropRect.x} y1={cropRect.y + cropRect.h * t}
          x2={cropRect.x + cropRect.w} y2={cropRect.y + cropRect.h * t}
          stroke="rgba(255,255,255,0.2)" stroke-width={strokeW * 0.7}
          pointer-events="none"
        />
      {/each}

      <!-- Interior move area (transparent, captures drag) -->
      <!-- svelte-ignore a11y-interactive-supports-focus -->
      <rect
        role="button"
        aria-label="Move crop region"
        x={cropRect.x + handleR * 1.5}
        y={cropRect.y + handleR * 1.5}
        width={Math.max(0, cropRect.w - handleR * 3)}
        height={Math.max(0, cropRect.h - handleR * 3)}
        fill="transparent"
        style="cursor: move;"
        on:mousedown={e => startDrag(e, 'move')}
      />

      <!-- Corner handles -->
      {#each handles as h}
        <!-- svelte-ignore a11y-interactive-supports-focus -->
        <circle
          role="button"
          aria-label="Resize crop {h.id}"
          cx={h.cx} cy={h.cy}
          r={handleR}
          fill="white"
          stroke="#6366f1"
          stroke-width={strokeW * 2}
          style="cursor: {h.cursor};"
          on:mousedown={e => startDrag(e, h.id)}
        />
      {/each}

      <!-- Crop size readout -->
      <text
        x={cropRect.x + cropRect.w / 2}
        y={cropRect.y - handleR * 1.5}
        fill="white"
        font-size={handleR * 1.6}
        font-family="monospace"
        text-anchor="middle"
        pointer-events="none"
      >{cropRect.w.toFixed(1)} × {cropRect.h.toFixed(1)}</text>
    {/if}
  </svg>
</div>

<style>
  .canvas-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #1a1d2e;
    border-radius: 8px;
    overflow: hidden;
  }

  .svg-host {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
  }

  .svg-host :global(svg) {
    max-width: 100%;
    max-height: 100%;
    width: 100% !important;
    height: 100% !important;
  }

  .overlay {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    padding: 16px;
  }

  .overlay.interactive {
    pointer-events: all;
  }
</style>
