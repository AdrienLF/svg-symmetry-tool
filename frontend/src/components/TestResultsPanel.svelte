<script>
  import { createEventDispatcher } from 'svelte';

  export let results = [];   // array from run_all_tests()
  export let loading = false;

  const dispatch = createEventDispatcher();

  $: passed = results.filter(r => r.passed).length;
  $: total  = results.length;

  const DIFFICULTY_COLOR = {
    easy:      '#10b981',
    medium:    '#f59e0b',
    hard:      '#f97316',
    very_hard: '#ef4444',
  };

  function fmt(v, decimals = 2) {
    return v == null ? '—' : Number(v).toFixed(decimals);
  }
</script>

<div class="panel-overlay">
  <div class="panel">
    <div class="panel-head">
      <h2>Symmetry Test Results</h2>
      {#if results.length > 0}
        <span class="summary" class:all-pass={passed === total}>
          {passed}/{total} passed
        </span>
      {/if}
      <button class="close-btn" on:click={() => dispatch('close')}>✕</button>
    </div>

    {#if loading}
      <div class="loading-msg">Running tests…</div>
    {:else if results.length === 0}
      <div class="loading-msg">No results yet.</div>
    {:else}
      <div class="grid">
        {#each results as r}
          <div class="card" class:card-pass={r.passed} class:card-fail={!r.passed}>
            <!-- Thumbnail -->
            <div class="thumb-wrap">
              <img class="thumb" src={r.svg_thumbnail} alt={r.label} />
            </div>

            <!-- Header row -->
            <div class="card-header">
              <span class="test-id">#{r.id}</span>
              <span class="diff-badge" style="color:{DIFFICULTY_COLOR[r.difficulty]}">
                {r.difficulty}
              </span>
              <span class="pass-badge" class:pass={r.passed} class:fail={!r.passed}>
                {r.passed ? '✓ pass' : '✗ fail'}
              </span>
            </div>

            <div class="card-label">{r.label}</div>

            {#if r.error}
              <div class="card-error">{r.error}</div>
            {:else}
              <table class="metrics">
                <tr>
                  <td class="mk">Angle expected</td>
                  <td class="mv">{fmt(r.expected_angle, 1)}°</td>
                </tr>
                <tr>
                  <td class="mk">Angle detected</td>
                  <td class="mv">{fmt(r.detected_angle, 2)}°</td>
                </tr>
                <tr>
                  <td class="mk">Angle error</td>
                  <td class="mv" class:good={r.angle_error <= r.angle_tolerance}
                                 class:bad={r.angle_error > r.angle_tolerance}>
                    {fmt(r.angle_error, 3)}° / ±{r.angle_tolerance}°
                  </td>
                </tr>
                <tr>
                  <td class="mk">Centre error</td>
                  <td class="mv" class:good={r.center_error <= r.center_tolerance}
                                 class:bad={r.center_error > r.center_tolerance}>
                    {fmt(r.center_error, 2)} px / ±{r.center_tolerance} px
                  </td>
                </tr>
                <tr>
                  <td class="mk">Symmetry score</td>
                  <td class="mv">{r.score != null ? (1 - r.score).toFixed(4) : '—'}</td>
                </tr>
              </table>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .panel-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    z-index: 100;
    padding: 24px 16px;
    overflow-y: auto;
  }

  .panel {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 12px;
    width: 100%;
    max-width: 1100px;
    padding: 24px;
  }

  .panel-head {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
  }

  .panel-head h2 {
    font-size: 16px;
    font-weight: 700;
    color: #e2e8f0;
    flex: 1;
  }

  .summary {
    font-size: 13px;
    font-weight: 600;
    color: #ef4444;
    background: #2d1b1b;
    border: 1px solid #7f1d1d;
    border-radius: 20px;
    padding: 3px 12px;
  }
  .summary.all-pass {
    color: #10b981;
    background: #0d2e22;
    border-color: #065f46;
  }

  .close-btn {
    background: transparent;
    border: 1px solid #334155;
    color: #94a3b8;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 14px;
    cursor: pointer;
  }
  .close-btn:hover { color: #e2e8f0; }

  .loading-msg {
    text-align: center;
    color: #64748b;
    padding: 40px 0;
    font-size: 14px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  .card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .card.card-pass { border-color: #065f46; }
  .card.card-fail { border-color: #7f1d1d; }

  .thumb-wrap {
    background: #1a1d2e;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
    height: 140px;
  }

  .thumb {
    max-width: 100%;
    max-height: 116px;
    object-fit: contain;
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px 4px;
  }

  .test-id {
    font-size: 11px;
    color: #475569;
    font-family: monospace;
  }

  .diff-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .pass-badge {
    margin-left: auto;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 20px;
  }
  .pass-badge.pass { color: #10b981; background: #0d2e22; }
  .pass-badge.fail { color: #ef4444; background: #2d1b1b; }

  .card-label {
    font-size: 12px;
    font-weight: 500;
    color: #cbd5e1;
    padding: 0 12px 8px;
    line-height: 1.4;
  }

  .card-error {
    font-size: 11px;
    color: #fca5a5;
    padding: 0 12px 10px;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .metrics {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    border-top: 1px solid #1e293b;
  }

  .metrics tr:not(:last-child) td { border-bottom: 1px solid #0f172a; }

  .mk {
    color: #64748b;
    padding: 4px 12px;
    width: 55%;
  }
  .mv {
    color: #e2e8f0;
    font-family: monospace;
    padding: 4px 12px 4px 0;
  }

  .mv.good { color: #10b981; }
  .mv.bad  { color: #ef4444; }
</style>
