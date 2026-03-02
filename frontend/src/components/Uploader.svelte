<script>
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();
  let dragging = false;
  let error = '';

  function handleFile(file) {
    if (!file) return;
    const name = file.name.toLowerCase();
    const type = file.type;
    if (!name.endsWith('.svg') && type !== 'image/svg+xml') {
      error = 'Please select an SVG file.';
      return;
    }
    error = '';
    dispatch('upload', file);
  }

  function onDrop(e) {
    e.preventDefault();
    dragging = false;
    handleFile(e.dataTransfer.files[0]);
  }

  function onInput(e) {
    handleFile(e.target.files[0]);
  }

  function onDragover(e) {
    e.preventDefault();
    dragging = true;
  }
</script>

<div
  class="uploader"
  class:dragging
  on:dragover={onDragover}
  on:dragleave={() => (dragging = false)}
  on:drop={onDrop}
  role="region"
  aria-label="File upload area"
>
  <div class="icon">⬡</div>
  <p class="title">Drop an SVG file here</p>
  <p class="sub">or</p>
  <label class="browse-btn">
    Browse file
    <input type="file" accept=".svg,image/svg+xml" on:change={onInput} />
  </label>
  {#if error}
    <p class="error">{error}</p>
  {/if}
</div>

<style>
  .uploader {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    width: 480px;
    height: 320px;
    border: 2px dashed #334155;
    border-radius: 16px;
    background: #1a1d2e;
    transition: border-color 0.2s, background 0.2s;
    cursor: default;
  }

  .uploader.dragging {
    border-color: #6366f1;
    background: #1e2040;
  }

  .icon {
    font-size: 48px;
    opacity: 0.4;
  }

  .title {
    font-size: 18px;
    font-weight: 600;
    color: #cbd5e1;
  }

  .sub {
    color: #64748b;
    font-size: 14px;
  }

  .browse-btn {
    display: inline-block;
    padding: 8px 20px;
    background: #6366f1;
    color: white;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
  }

  .browse-btn:hover {
    background: #4f46e5;
  }

  .browse-btn input {
    display: none;
  }

  .error {
    color: #f87171;
    font-size: 13px;
  }
</style>
