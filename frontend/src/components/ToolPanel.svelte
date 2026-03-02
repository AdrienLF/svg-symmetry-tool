<script>
  import { createEventDispatcher } from 'svelte';

  export let phase = 'idle';
  export let cropMode = false;
  export let widthMm = 6.0;
  export let showWidth = false;
  export let axisInfo = null;
  export let loading = false;
  export let error = '';
  export let fileName = '';

  const dispatch = createEventDispatcher();

  // Compute a human-readable description of which side is which
  // based on the axis angle: if axis is ~vertical, positive normal points "right"
  $: axisDeg = axisInfo ? axisInfo.angle_deg : 0;
  $: {
    // Axis direction = (cos θ, sin θ)  →  normal = (-sin θ, cos θ)
    // "positive" normal: if axis is vertical (90°), normal points left (−x)
    // We label sides by where the normal points
    const θ = (axisDeg * Math.PI) / 180;
    const nx = -Math.sin(θ);
    const ny = Math.cos(θ);
    // SVG y-axis is flipped: positive y is down
    sidePositiveLabel = nx > 0.3 ? 'Right half' : nx < -0.3 ? 'Left half' : ny < -0.3 ? 'Top half' : 'Bottom half';
    sideNegativeLabel = nx > 0.3 ? 'Left half' : nx < -0.3 ? 'Right half' : ny < -0.3 ? 'Bottom half' : 'Top half';
  }
  let sidePositiveLabel = 'Positive side';
  let sideNegativeLabel = 'Negative side';

  $: canCrop = phase !== 'idle' && !loading;

  // Phase helpers
  $: canConvert = phase === 'uploaded' && !loading;
  $: canDetect = (phase === 'converted' || phase === 'symmetry_detected' || phase === 'fixed') && !loading;
  $: canFix = phase === 'symmetry_detected' && !loading;
  $: canWidth = (phase === 'converted' || phase === 'symmetry_detected' || phase === 'fixed') && !loading;
  $: canExport = phase !== 'idle' && !loading;

  function onWidthChange(e) {
    const val = parseFloat(e.target.value);
    if (!isNaN(val) && val > 0) {
      dispatch('widthChange', val);
    }
  }
</script>

<aside class="panel">
  <div class="panel-header">
    <h1 class="app-title">SVG Symmetry Tool</h1>
    {#if fileName}
      <span class="filename">{fileName}</span>
    {/if}
  </div>

  <!-- Crop tool (available at any phase after upload) -->
  {#if phase !== 'idle'}
  <section class="step crop-step" class:crop-active={cropMode} class:active={!cropMode && canCrop}>
    <div class="step-header">
      <span class="step-num crop-num">✂</span>
      <h2>Crop</h2>
      {#if cropMode}<span class="badge crop-badge">editing</span>{/if}
    </div>
    {#if !cropMode}
      <p class="step-desc">Trim away unwanted areas before analysis.</p>
      <button class="btn secondary" disabled={!canCrop} on:click={() => dispatch('enterCrop')}>
        Crop SVG…
      </button>
    {:else}
      <p class="step-desc">Drag the handles to set the crop area, then apply.</p>
      <div class="btn-row">
        <button class="btn primary" disabled={loading} on:click={() => dispatch('applyCrop')}>
          {loading ? '⟳ Cropping…' : 'Apply crop'}
        </button>
        <button class="btn ghost inline" on:click={() => dispatch('cancelCrop')}>
          Cancel
        </button>
      </div>
    {/if}
  </section>
  {/if}

  <!-- Step 1: Convert shapes to paths -->
  <section class="step" class:active={phase === 'uploaded'} class:done={['converted','symmetry_detected','fixed'].includes(phase)}>
    <div class="step-header">
      <span class="step-num">1</span>
      <h2>Convert to Paths</h2>
      {#if ['converted','symmetry_detected','fixed'].includes(phase)}<span class="badge done-badge">✓</span>{/if}
    </div>
    <p class="step-desc">Replace all shape elements (rect, circle, ellipse, …) with equivalent path elements.</p>
    <button
      class="btn primary"
      disabled={!canConvert}
      on:click={() => dispatch('convert')}
    >
      {loading && phase === 'uploaded' ? '⟳ Converting…' : 'Convert shapes'}
    </button>
  </section>

  <!-- Step 2: Detect symmetry -->
  <section class="step" class:active={phase === 'converted'} class:done={['symmetry_detected','fixed'].includes(phase)}>
    <div class="step-header">
      <span class="step-num">2</span>
      <h2>Detect Symmetry Axis</h2>
      {#if ['symmetry_detected','fixed'].includes(phase)}<span class="badge done-badge">✓</span>{/if}
    </div>
    <p class="step-desc">Find the best-fit axis of symmetry using geometric optimisation.</p>
    <button
      class="btn primary"
      disabled={!canDetect}
      on:click={() => dispatch('detectSymmetry')}
    >
      {loading && phase === 'converted' ? '⟳ Detecting…' : 'Detect axis'}
    </button>

    {#if axisInfo}
      <div class="info-box">
        <div class="info-row">
          <span class="label">Angle</span>
          <span class="value">{axisInfo.angle_deg.toFixed(2)}°</span>
        </div>
        <div class="info-row">
          <span class="label">Centre</span>
          <span class="value">({axisInfo.cx.toFixed(1)}, {axisInfo.cy.toFixed(1)})</span>
        </div>
        <div class="info-row">
          <span class="label">Score</span>
          <span class="value">{axisInfo.score.toExponential(3)}</span>
        </div>
        <p class="hint">Lower score = more symmetric. Re-run after fixing to verify.</p>
      </div>

      <!-- Manual axis adjustment -->
      <div class="adjust-group">
        <label class="adjust-label">
          Axis angle (°)
          <input
            type="number"
            step="0.1"
            value={axisInfo.angle_deg.toFixed(2)}
            on:change={e => dispatch('adjustAxis', { angle_deg: parseFloat(e.target.value), cx: axisInfo.cx, cy: axisInfo.cy })}
          />
        </label>
      </div>
    {/if}
  </section>

  <!-- Step 3: Fix symmetry -->
  {#if phase === 'symmetry_detected' || phase === 'fixed'}
  <section class="step" class:active={phase === 'symmetry_detected'} class:done={phase === 'fixed'}>
    <div class="step-header">
      <span class="step-num">3</span>
      <h2>Fix Symmetry</h2>
      {#if phase === 'fixed'}<span class="badge done-badge">✓</span>{/if}
    </div>
    <p class="step-desc">
      Mirror one side of the design across the axis. Pick the side you want to <em>keep</em>.
    </p>
    <div class="btn-row">
      <button class="btn secondary" disabled={!canFix} on:click={() => dispatch('fix', 'positive')}>
        {sidePositiveLabel}
      </button>
      <button class="btn secondary" disabled={!canFix} on:click={() => dispatch('fix', 'negative')}>
        {sideNegativeLabel}
      </button>
    </div>
  </section>
  {/if}

  <!-- Width visualisation -->
  <section class="step" class:active={canWidth}>
    <div class="step-header">
      <span class="step-num">⬡</span>
      <h2>Bit Width Preview</h2>
    </div>
    <p class="step-desc">Visualise the area removed by your CNC bit (Shaper Origin).</p>

    <label class="adjust-label">
      Bit diameter (mm)
      <input
        type="number"
        min="0.1"
        max="50"
        step="0.1"
        value={widthMm}
        on:change={onWidthChange}
        disabled={!canWidth}
      />
    </label>

    <label class="toggle-label">
      <input
        type="checkbox"
        checked={showWidth}
        on:change={() => dispatch('toggleWidth')}
        disabled={!canWidth}
      />
      <span>Show width overlay</span>
    </label>
  </section>

  <!-- Export -->
  <section class="step export-section">
    <button
      class="btn export-btn"
      disabled={!canExport}
      on:click={() => dispatch('export')}
    >
      ↓ Export SVG
    </button>
    <button
      class="btn ghost"
      on:click={() => dispatch('reset')}
    >
      Reset
    </button>
    <button
      class="btn ghost test-btn"
      disabled={loading}
      on:click={() => dispatch('runTests')}
    >
      ⚗ Run symmetry tests
    </button>
  </section>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}

  {#if loading}
    <div class="loading-bar"></div>
  {/if}
</aside>

<style>
  .panel {
    width: 300px;
    min-width: 280px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 0;
    background: #111827;
    border-right: 1px solid #1e293b;
    overflow-y: auto;
    padding-bottom: 16px;
    position: relative;
  }

  .panel-header {
    padding: 16px 20px 12px;
    border-bottom: 1px solid #1e293b;
  }

  .app-title {
    font-size: 16px;
    font-weight: 700;
    color: #e2e8f0;
    letter-spacing: -0.02em;
  }

  .filename {
    display: block;
    font-size: 11px;
    color: #64748b;
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .step {
    padding: 16px 20px;
    border-bottom: 1px solid #1e293b;
    opacity: 0.5;
    transition: opacity 0.2s;
  }

  .step.active,
  .step.done {
    opacity: 1;
  }

  .step-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .step-num {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #334155;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8;
    flex-shrink: 0;
  }

  .step.active .step-num {
    background: #6366f1;
    color: white;
  }

  .step.done .step-num {
    background: #10b981;
    color: white;
  }

  h2 {
    font-size: 13px;
    font-weight: 600;
    color: #cbd5e1;
  }

  .badge {
    margin-left: auto;
    font-size: 11px;
  }

  .done-badge { color: #10b981; }

  .step-desc {
    font-size: 12px;
    color: #64748b;
    line-height: 1.5;
    margin-bottom: 10px;
  }

  .btn {
    display: block;
    width: 100%;
    padding: 8px 12px;
    border-radius: 6px;
    border: none;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, opacity 0.15s;
    text-align: center;
  }

  .btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .btn.primary {
    background: #6366f1;
    color: white;
  }
  .btn.primary:not(:disabled):hover { background: #4f46e5; }

  .btn.secondary {
    background: #1e293b;
    color: #cbd5e1;
    border: 1px solid #334155;
  }
  .btn.secondary:not(:disabled):hover { background: #263348; }

  .btn.ghost {
    background: transparent;
    color: #64748b;
    border: 1px solid #1e293b;
    margin-top: 6px;
  }
  .btn.ghost:hover { color: #94a3b8; }

  .btn.export-btn {
    background: #0f766e;
    color: white;
  }
  .btn.export-btn:not(:disabled):hover { background: #0d6960; }

  .btn-row {
    display: flex;
    gap: 8px;
  }
  .btn-row .btn { flex: 1; }

  .info-box {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 10px 12px;
    margin-top: 10px;
    font-size: 12px;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
  }

  .label { color: #64748b; }
  .value { color: #e2e8f0; font-family: monospace; }

  .hint {
    margin-top: 6px;
    font-size: 11px;
    color: #475569;
    font-style: italic;
  }

  .adjust-group, .toggle-label {
    margin-top: 10px;
  }

  .adjust-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    color: #94a3b8;
  }

  .adjust-label input[type="number"] {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e2e8f0;
    font-size: 13px;
    width: 100%;
    outline: none;
  }
  .adjust-label input[type="number"]:focus { border-color: #6366f1; }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #94a3b8;
    cursor: pointer;
    user-select: none;
  }

  .toggle-label input[type="checkbox"] {
    accent-color: #6366f1;
    width: 14px;
    height: 14px;
  }

  .crop-step {
    opacity: 1 !important; /* always visible after upload */
    border-left: 2px solid transparent;
    transition: border-color 0.2s, background 0.2s;
  }

  .crop-step.crop-active {
    border-left-color: #f59e0b;
    background: #1c1a10;
  }

  .crop-num {
    background: #78350f !important;
    color: #fcd34d !important;
  }

  .crop-step.crop-active .crop-num {
    background: #f59e0b !important;
    color: #1c1400 !important;
  }

  .crop-badge {
    color: #f59e0b;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .btn.inline {
    flex: 0 0 auto;
    width: auto;
    padding: 8px 14px;
    margin-top: 0;
  }

  .export-section {
    opacity: 1 !important;
    border-bottom: none;
  }

  .test-btn {
    color: #a78bfa;
    border-color: #312e81;
  }
  .test-btn:hover:not(:disabled) { color: #c4b5fd; background: #1e1b4b; }

  .error-box {
    margin: 8px 20px;
    padding: 10px 12px;
    background: #2d1b1b;
    border: 1px solid #7f1d1d;
    border-radius: 6px;
    font-size: 12px;
    color: #fca5a5;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .loading-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, #6366f1, #a855f7, #6366f1);
    background-size: 200% 100%;
    animation: slide 1.4s linear infinite;
  }

  @keyframes slide {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
</style>
