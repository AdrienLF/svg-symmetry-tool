<script>
  import Uploader from './components/Uploader.svelte';
  import SvgCanvas from './components/SvgCanvas.svelte';
  import ToolPanel from './components/ToolPanel.svelte';
  import TestResultsPanel from './components/TestResultsPanel.svelte';
  import * as api from './lib/api.js';

  // ── State ──────────────────────────────────────────────────────────────────
  let phase = 'idle';           // 'idle' | 'uploaded' | 'converted' | 'symmetry_detected' | 'fixed'
  let svgContent = '';          // current working SVG (mutated at each step)
  let originalSvg = '';         // preserved for reset
  let convertedSvg = '';        // version after path conversion (base for symmetry/width ops)
  let viewBox = [0, 0, 500, 500];
  let pxPerMm = 3.7795;
  let axisInfo = null;
  let widthMm = 6.0;
  let showWidth = false;
  let widthSvg = '';            // SVG with width overlay
  let loading = false;
  let error = '';
  let fileName = '';

  // Crop state
  let cropMode = false;
  let cropRect = null;          // { x, y, w, h } in SVG user coords

  // Test panel state
  let showTests = false;
  let testResults = [];
  let testLoading = false;

  // What to show: crop mode always uses base SVG, otherwise use width overlay if active
  $: displaySvg = cropMode ? svgContent : (showWidth && widthSvg ? widthSvg : svgContent);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function setError(msg) {
    error = msg;
    loading = false;
  }

  function clearError() { error = ''; }

  // ── Handlers ───────────────────────────────────────────────────────────────
  async function handleUpload(file) {
    clearError();
    loading = true;
    fileName = file.name;
    try {
      const result = await api.uploadSvg(file);
      svgContent = result.svg_content;
      originalSvg = result.svg_content;
      viewBox = result.viewBox || [0, 0, 500, 500];
      pxPerMm = result.px_per_mm || 3.7795;
      phase = 'uploaded';
      axisInfo = null;
      showWidth = false;
      widthSvg = '';
    } catch (e) {
      setError(`Upload failed: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  async function handleConvert() {
    clearError();
    loading = true;
    try {
      const result = await api.convertToPaths(svgContent);
      svgContent = result.svg_content;
      convertedSvg = result.svg_content;
      phase = 'converted';
      showWidth = false;
      widthSvg = '';
    } catch (e) {
      setError(`Conversion failed: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  async function handleDetectSymmetry() {
    clearError();
    loading = true;
    try {
      // Always detect on the converted SVG (without width overlay)
      const baseSvg = convertedSvg || svgContent;
      const result = await api.detectSymmetry(baseSvg, pxPerMm, viewBox);
      axisInfo = result;
      phase = 'symmetry_detected';
    } catch (e) {
      setError(`Symmetry detection failed: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  async function handleFix(event) {
    const keepSide = event.detail; // 'positive' | 'negative'
    clearError();
    loading = true;
    try {
      const baseSvg = convertedSvg || svgContent;
      const result = await api.fixSymmetry(
        baseSvg,
        axisInfo.angle_deg,
        axisInfo.cx,
        axisInfo.cy,
        keepSide,
      );
      svgContent = result.svg_content;
      convertedSvg = result.svg_content;
      phase = 'fixed';
      showWidth = false;
      widthSvg = '';
      axisInfo = null; // clear axis overlay; user can re-detect to verify
    } catch (e) {
      setError(`Symmetry fix failed: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  async function handleToggleWidth() {
    if (!showWidth) {
      // Turning on: fetch width overlay
      clearError();
      loading = true;
      try {
        const baseSvg = convertedSvg || svgContent;
        const result = await api.visualizeWidth(baseSvg, widthMm, pxPerMm);
        widthSvg = result.svg_content;
        showWidth = true;
      } catch (e) {
        setError(`Width preview failed: ${e.message}`);
      } finally {
        loading = false;
      }
    } else {
      showWidth = false;
    }
  }

  async function handleWidthChange(event) {
    widthMm = event.detail;
    if (showWidth) {
      // Re-fetch with new width
      showWidth = false;
      await handleToggleWidth();
    }
  }

  function handleAdjustAxis(event) {
    if (!axisInfo) return;
    axisInfo = { ...axisInfo, ...event.detail };
    // Recompute axis endpoints from new angle
    const θ = (axisInfo.angle_deg * Math.PI) / 180;
    const span = Math.sqrt(viewBox[2] ** 2 + viewBox[3] ** 2) * 1.5;
    const ux = Math.cos(θ), uy = Math.sin(θ);
    axisInfo.axis_p1 = [axisInfo.cx - span * ux, axisInfo.cy - span * uy];
    axisInfo.axis_p2 = [axisInfo.cx + span * ux, axisInfo.cy + span * uy];
    axisInfo = axisInfo; // trigger reactivity
  }

  function handleExport() {
    // Download the current svgContent as a file
    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const baseName = fileName.replace(/\.svg$/i, '') || 'output';
    a.download = `${baseName}_processed.svg`;
    a.href = url;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Crop handlers ───────────────────────────────────────────────────────────
  function handleEnterCrop() {
    // Initialise crop rect to the full current viewBox
    cropRect = { x: viewBox[0], y: viewBox[1], w: viewBox[2], h: viewBox[3] };
    cropMode = true;
    showWidth = false; // hide width overlay while cropping
  }

  function handleCancelCrop() {
    cropMode = false;
    cropRect = null;
  }

  async function handleApplyCrop() {
    if (!cropRect) return;
    clearError();
    loading = true;
    try {
      const result = await api.cropSvg(
        svgContent,
        cropRect.x, cropRect.y,
        cropRect.w, cropRect.h,
      );
      svgContent = result.svg_content;
      viewBox = result.viewBox;
      // Crop auto-converts shapes → treat result as converted regardless of prior phase
      convertedSvg = result.svg_content;
      if (phase === 'uploaded' || phase === 'converted') {
        phase = 'converted';
      } else {
        // symmetry_detected / fixed → invalidate, go back to converted
        phase = 'converted';
      }
      axisInfo = null;
      showWidth = false;
      widthSvg = '';
      cropMode = false;
      cropRect = null;
    } catch (e) {
      setError(`Crop failed: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  async function handleRunTests() {
    showTests = true;
    testLoading = true;
    testResults = [];
    try {
      const data = await api.runSymmetryTests();
      testResults = data.results;
    } catch (e) {
      setError(`Tests failed: ${e.message}`);
      showTests = false;
    } finally {
      testLoading = false;
    }
  }

  function handleReset() {
    svgContent = originalSvg;
    convertedSvg = '';
    phase = 'uploaded';
    axisInfo = null;
    showWidth = false;
    widthSvg = '';
    cropMode = false;
    cropRect = null;
    error = '';
  }
</script>

<main class="app">
  {#if phase === 'idle'}
    <div class="splash">
      <Uploader on:upload={e => handleUpload(e.detail)} />
    </div>
  {:else}
    <div class="workspace">
      <ToolPanel
        {phase}
        {cropMode}
        {widthMm}
        {showWidth}
        {axisInfo}
        {loading}
        {error}
        {fileName}
        on:enterCrop={handleEnterCrop}
        on:cancelCrop={handleCancelCrop}
        on:applyCrop={handleApplyCrop}
        on:convert={handleConvert}
        on:detectSymmetry={handleDetectSymmetry}
        on:fix={handleFix}
        on:toggleWidth={handleToggleWidth}
        on:widthChange={handleWidthChange}
        on:adjustAxis={handleAdjustAxis}
        on:export={handleExport}
        on:reset={handleReset}
        on:runTests={handleRunTests}
      />
      <div class="canvas-area">
        <SvgCanvas
          svgContent={displaySvg}
          axis={cropMode ? null : axisInfo}
          {viewBox}
          {cropMode}
          bind:cropRect
        />
      </div>
    </div>
  {/if}

  {#if showTests}
    <TestResultsPanel
      results={testResults}
      loading={testLoading}
      on:close={() => { showTests = false; testResults = []; }}
    />
  {/if}
</main>

<style>
  .app {
    height: 100vh;
    display: flex;
    overflow: hidden;
  }

  .splash {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(ellipse at center, #1a1d2e 0%, #0f1117 100%);
  }

  .workspace {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .canvas-area {
    flex: 1;
    padding: 16px;
    overflow: hidden;
  }
</style>
