/**
 * RD STUDIO — AUTO SILENCE REMOVER
 * Professional Client Application Engine & Waveform Visualizer
 * Owner: Shahneel Khan | Website: rdstudio.online
 */

// Application State
const state = {
  currentMedia: null,       // Metadata dict from server
  waveformPeaks: [],        // Downsampled float peaks [0.0 - 1.0]
  silenceRegions: [],       // Detected silence regions [{start, end, duration}]
  analysisResult: null,     // Analysis summary metrics
  activePresetId: 'rd_studio_dialogue_cut',
  presets: [],
  settings: {},
  zoomLevel: 1.0,
  scrollOffset: 0.0,
  playheadPosition: 0.0,    // Current playhead in seconds
  isPlayingOriginal: false,
  isPlayingProcessed: false,
  processedFilePath: null,
  pollTimer: null,
  batchPollTimer: null,
};

// DOM Element References
const el = {
  dropZone: document.getElementById('drop-zone'),
  mediaView: document.getElementById('media-view'),
  btnBrowse: document.getElementById('btn-browse'),
  fileInputFallback: document.getElementById('file-input-fallback'),
  btnClearMedia: document.getElementById('btn-clear-media'),
  btnAddBatch: document.getElementById('btn-add-batch'),

  // Metadata
  metaType: document.getElementById('meta-type'),
  metaFilename: document.getElementById('meta-filename'),
  metaPath: document.getElementById('meta-path'),
  metaDuration: document.getElementById('meta-duration'),
  metaSize: document.getElementById('meta-size'),
  metaSamplerate: document.getElementById('meta-samplerate'),
  metaChannels: document.getElementById('meta-channels'),
  metaCodec: document.getElementById('meta-codec'),

  // Waveform
  canvasViewport: document.getElementById('canvas-viewport'),
  waveformCanvas: document.getElementById('waveform-canvas'),
  playheadLine: document.getElementById('playhead-line'),
  waveCurrentTime: document.getElementById('wave-current-time'),
  waveTotalTime: document.getElementById('wave-total-time'),
  btnZoomIn: document.getElementById('btn-zoom-in'),
  btnZoomOut: document.getElementById('btn-zoom-out'),
  btnZoomReset: document.getElementById('btn-zoom-reset'),
  zoomLevelDisplay: document.getElementById('zoom-level'),

  // Analysis Banner
  analysisBanner: document.getElementById('analysis-banner'),
  statRegions: document.getElementById('stat-regions'),
  statTotalSilence: document.getElementById('stat-total-silence'),
  statReduction: document.getElementById('stat-reduction'),
  statEstimatedOut: document.getElementById('stat-estimated-out'),

  // Silence Controls
  presetSelect: document.getElementById('preset-select'),
  btnSavePresetPrompt: document.getElementById('btn-save-preset-prompt'),
  sliderThreshold: document.getElementById('slider-threshold'),
  inputThreshold: document.getElementById('input-threshold'),
  inputMinDuration: document.getElementById('input-min-duration'),
  selectAction: document.getElementById('select-action'),
  rowRemainingSilence: document.getElementById('row-remaining-silence'),
  inputRemainingSilence: document.getElementById('input-remaining-silence'),
  checkMaxSilence: document.getElementById('check-max-silence'),
  maxSilenceInputContainer: document.getElementById('max-silence-input-container'),
  inputMaxSilence: document.getElementById('input-max-silence'),

  // Execution & Export
  btnAnalyze: document.getElementById('btn-analyze'),
  btnProcess: document.getElementById('btn-process'),
  exportFormat: document.getElementById('export-format'),
  exportQuality: document.getElementById('export-quality'),
  exportSamplerate: document.getElementById('export-samplerate'),
  exportChannels: document.getElementById('export-channels'),
  exportTargetDisplay: document.getElementById('export-target-display'),
  btnChangeFolder: document.getElementById('btn-change-folder'),

  // Audio Players
  origTimer: document.getElementById('orig-timer'),
  btnOrigPlay: document.getElementById('btn-orig-play'),
  btnOrigStop: document.getElementById('btn-orig-stop'),
  origSeek: document.getElementById('orig-seek'),
  origSpeed: document.getElementById('orig-speed'),
  origVol: document.getElementById('orig-vol'),

  procControls: document.getElementById('proc-controls'),
  procTimer: document.getElementById('proc-timer'),
  btnProcPlay: document.getElementById('btn-proc-play'),
  btnProcStop: document.getElementById('btn-proc-stop'),
  procSeek: document.getElementById('proc-seek'),
  procSpeed: document.getElementById('proc-speed'),
  procVol: document.getElementById('proc-vol'),

  // Progress Modal
  progressModal: document.getElementById('progress-modal'),
  progFilename: document.getElementById('prog-filename'),
  progBarFill: document.getElementById('prog-bar-fill'),
  progPct: document.getElementById('prog-pct'),
  progStage: document.getElementById('prog-stage'),
  progElapsed: document.getElementById('prog-elapsed'),
  progRemaining: document.getElementById('prog-remaining'),
  progProcessedTime: document.getElementById('prog-processed-time'),
  btnCancelProcess: document.getElementById('btn-cancel-process'),

  // Modals & Navigation
  btnBatchToggle: document.getElementById('btn-batch-toggle'),
  batchModal: document.getElementById('batch-modal'),
  batchCounter: document.getElementById('batch-counter'),
  batchTableBody: document.getElementById('batch-table-body'),
  btnBatchAddFiles: document.getElementById('btn-batch-add-files'),
  btnBatchClear: document.getElementById('btn-batch-clear'),
  btnBatchProcessAll: document.getElementById('btn-batch-process-all'),

  btnPresetsModal: document.getElementById('btn-presets-modal'),
  presetsModal: document.getElementById('presets-modal'),
  presetsManagerList: document.getElementById('presets-manager-list'),
  savePresetModal: document.getElementById('save-preset-modal'),
  customPresetName: document.getElementById('custom-preset-name'),
  btnConfirmSavePreset: document.getElementById('btn-confirm-save-preset'),

  btnHistoryModal: document.getElementById('btn-history-modal'),
  historyModal: document.getElementById('history-modal'),
  historyTableBody: document.getElementById('history-table-body'),
  btnClearHistory: document.getElementById('btn-clear-history'),

  btnSettingsModal: document.getElementById('btn-settings-modal'),
  settingsModal: document.getElementById('settings-modal'),
  settingExportDir: document.getElementById('setting-export-dir'),
  settingTempDir: document.getElementById('setting-temp-dir'),
  settingAutoClean: document.getElementById('setting-auto-clean'),
  settingConfirmOverwrite: document.getElementById('setting-confirm-overwrite'),
  btnBrowseSettingExport: document.getElementById('btn-browse-setting-export'),
  btnSaveSettings: document.getElementById('btn-save-settings'),

  btnAboutModal: document.getElementById('btn-about-modal'),
  aboutModal: document.getElementById('about-modal'),
  globalStatusText: document.getElementById('global-status-text'),
};

// Real HTML5 Audio Objects
const audioOriginal = new Audio();
const audioProcessed = new Audio();

// --- Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadStatus();
  await loadSettings();
  await loadPresets();
  setupCanvasResize();
  updateBatchBadge();
});

// --- API Helpers ---
async function api(endpoint, options = {}) {
  try {
    const res = await fetch(endpoint, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
      throw new Error(err.error || `Request failed with status ${res.status}`);
    }
    return await res.json();
  } catch (error) {
    console.error(`API error on ${endpoint}:`, error);
    showStatus(error.message, true);
    throw error;
  }
}

function showStatus(msg, isError = false) {
  if (el.globalStatusText) {
    el.globalStatusText.textContent = msg;
    el.globalStatusText.style.color = isError ? '#ff4d5a' : '#8b92a5';
  }
}

// --- Load Presets & Settings ---
async function loadStatus() {
  try {
    const data = await api('/api/status');
    populateExportFormats(data.export_formats);
  } catch (e) {
    console.error('Failed to load status:', e);
  }
}

async function loadSettings() {
  try {
    const data = await api('/api/settings');
    state.settings = data.settings || {};
    if (el.exportTargetDisplay) {
      el.exportTargetDisplay.textContent = state.settings.export_dir || 'Music\\RD_Studio_Exports';
      el.exportTargetDisplay.title = state.settings.export_dir || '';
    }
    if (el.settingExportDir) el.settingExportDir.value = state.settings.export_dir || '';
    if (el.settingTempDir) el.settingTempDir.value = state.settings.temp_dir || '';
    if (el.settingAutoClean) el.settingAutoClean.checked = state.settings.auto_clean_temp !== false;
    if (el.settingConfirmOverwrite) el.settingConfirmOverwrite.checked = state.settings.confirm_overwrite !== false;
  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

async function loadPresets() {
  try {
    const data = await api('/api/presets');
    state.presets = data.presets || [];
    renderPresetDropdown();
    renderPresetsManager();
    // Default preset is RD Studio Dialogue Silence Cut
    selectPreset('rd_studio_dialogue_cut');
  } catch (e) {
    console.error('Failed to load presets:', e);
  }
}

function renderPresetDropdown() {
  el.presetSelect.innerHTML = '';
  state.presets.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    el.presetSelect.appendChild(opt);
  });
}

function selectPreset(presetId) {
  const p = state.presets.find(item => item.id === presetId);
  if (!p) return;
  state.activePresetId = presetId;
  el.presetSelect.value = presetId;

  // Apply settings to UI controls
  el.sliderThreshold.value = p.threshold_db;
  el.inputThreshold.value = parseFloat(p.threshold_db).toFixed(2);
  el.inputMinDuration.value = p.min_silence_sec;
  el.selectAction.value = p.action || 'truncate';
  el.inputRemainingSilence.value = p.remaining_silence_sec;

  // Max silence
  if (p.max_silence_sec) {
    el.checkMaxSilence.checked = true;
    el.inputMaxSilence.value = p.max_silence_sec;
    el.maxSilenceInputContainer.style.opacity = '1';
    el.maxSilenceInputContainer.style.pointerEvents = 'auto';
  } else {
    el.checkMaxSilence.checked = false;
    el.maxSilenceInputContainer.style.opacity = '0.4';
    el.maxSilenceInputContainer.style.pointerEvents = 'none';
  }

  updateActionVisibility();
  updateActiveChips();
}

function updateActionVisibility() {
  const action = el.selectAction.value;
  if (action === 'remove') {
    el.rowRemainingSilence.style.opacity = '0.35';
    el.rowRemainingSilence.style.pointerEvents = 'none';
  } else {
    el.rowRemainingSilence.style.opacity = '1';
    el.rowRemainingSilence.style.pointerEvents = 'auto';
  }
}

function updateActiveChips() {
  const minDur = parseFloat(el.inputMinDuration.value);
  const remDur = parseFloat(el.inputRemainingSilence.value);

  document.querySelectorAll('.chip').forEach(chip => {
    const target = chip.getAttribute('data-target');
    const val = parseFloat(chip.getAttribute('data-val'));
    if (target === 'input-min-duration') {
      chip.classList.toggle('active', Math.abs(minDur - val) < 0.005);
    } else if (target === 'input-remaining-silence') {
      chip.classList.toggle('active', Math.abs(remDur - val) < 0.005);
    }
  });
}

// --- Export Formats Setup ---
let exportFormatsConfig = {};
function populateExportFormats(formats) {
  exportFormatsConfig = formats || {};
  el.exportFormat.innerHTML = '';
  for (const [key, info] of Object.entries(exportFormatsConfig)) {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = info.name;
    el.exportFormat.appendChild(opt);
  }
  updateExportQualityOptions();
}

function updateExportQualityOptions() {
  const selectedFormat = el.exportFormat.value;
  const info = exportFormatsConfig[selectedFormat];
  el.exportQuality.innerHTML = '';
  if (!info || !info.qualities) return;

  info.qualities.forEach(q => {
    const opt = document.createElement('option');
    opt.value = q.id;
    opt.textContent = q.label;
    el.exportQuality.appendChild(opt);
  });

  if (info.default_quality) {
    el.exportQuality.value = info.default_quality;
  }
}

// --- File Import & Handling ---
async function handleFileSelected(filepath) {
  showStatus('Probing media file metadata...');
  try {
    const data = await api('/api/file/probe', {
      method: 'POST',
      body: JSON.stringify({ filepath })
    });
    setLoadedMedia(data.media_info);
  } catch (e) {
    alert(`Could not load media: ${e.message}`);
  }
}

async function handleFileUpload(fileObj) {
  showStatus(`Uploading ${fileObj.name}...`);
  const formData = new FormData();
  formData.append('file', fileObj);

  try {
    const res = await fetch('/api/file/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed.');
    setLoadedMedia(data.media_info);
  } catch (e) {
    alert(`Failed to upload file: ${e.message}`);
  }
}

async function setLoadedMedia(info) {
  state.currentMedia = info;
  state.silenceRegions = [];
  state.analysisResult = null;
  state.processedFilePath = null;
  state.zoomLevel = 1.0;
  state.playheadPosition = 0.0;

  // Update UI Info
  el.dropZone.classList.add('hidden');
  el.mediaView.classList.remove('hidden');

  el.metaType.textContent = info.is_video ? 'VIDEO STEM' : 'AUDIO TRACK';
  el.metaType.style.background = info.is_video ? '#00b0ff' : '#e50914';
  el.metaFilename.textContent = info.filename;
  el.metaFilename.title = info.filename;
  el.metaPath.textContent = info.filepath;
  el.metaPath.title = info.filepath;
  el.metaDuration.textContent = info.duration_formatted;
  el.metaSize.textContent = info.filesize_formatted;
  el.metaSamplerate.textContent = `${(info.sample_rate / 1000).toFixed(1)} kHz`;
  el.metaChannels.textContent = info.channel_layout || (info.channels === 1 ? 'Mono' : 'Stereo');
  el.metaCodec.textContent = `${info.audio_codec} (${info.bit_depth})`;

  el.waveTotalTime.textContent = info.duration_formatted;
  el.waveCurrentTime.textContent = '00:00:00.0';

  // Reset Analysis Banner
  el.analysisBanner.classList.add('hidden');

  // Reset Audio Players
  audioOriginal.src = `/api/stream/audio?file=${encodeURIComponent(info.filepath)}`;
  audioOriginal.load();
  el.origTimer.textContent = `00:00 / ${info.duration_formatted.slice(0, 5)}`;
  el.origSeek.value = 0;

  audioProcessed.src = '';
  el.procControls.style.opacity = '0.4';
  el.procControls.style.pointerEvents = 'none';
  el.procTimer.textContent = '--:-- / --:--';
  el.procSeek.value = 0;

  // Request Waveform Peaks
  await fetchWaveformPeaks(info.filepath);
  showStatus(`Loaded ${info.filename} (${info.duration_formatted})`);
}

async function fetchWaveformPeaks(filepath) {
  showStatus('Generating downsampled audio waveform...');
  try {
    const data = await api('/api/file/waveform', {
      method: 'POST',
      body: JSON.stringify({ filepath, target_peaks: 2000 })
    });
    state.waveformPeaks = data.peaks || [];
    renderWaveform();
    showStatus('Waveform loaded. Ready to analyze.');
  } catch (e) {
    console.error('Failed to generate waveform peaks:', e);
  }
}

function clearMedia() {
  audioOriginal.pause();
  audioProcessed.pause();
  audioOriginal.src = '';
  audioProcessed.src = '';

  state.currentMedia = null;
  state.waveformPeaks = [];
  state.silenceRegions = [];
  state.analysisResult = null;
  state.processedFilePath = null;

  el.mediaView.classList.add('hidden');
  el.dropZone.classList.remove('hidden');
  showStatus('Ready');
}

// --- Waveform Canvas Visualization ---
function setupCanvasResize() {
  const resizeObserver = new ResizeObserver(() => {
    if (state.waveformPeaks.length > 0) {
      renderWaveform();
    }
  });
  resizeObserver.observe(el.canvasViewport);
}

function renderWaveform() {
  const canvas = el.waveformCanvas;
  const dpr = window.devicePixelRatio || 1;
  const rect = el.canvasViewport.getBoundingClientRect();

  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;

  // Background
  ctx.fillStyle = '#090a0e';
  ctx.fillRect(0, 0, w, h);

  // Grid lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
  ctx.lineWidth = 1;
  const gridLines = 8;
  for (let i = 1; i < gridLines; i++) {
    const x = (w / gridLines) * i;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }

  // Center line
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  ctx.beginPath();
  ctx.moveTo(0, h / 2);
  ctx.lineTo(w, h / 2);
  ctx.stroke();

  const totalDuration = state.currentMedia ? state.currentMedia.duration : 1;
  const peaks = state.waveformPeaks;
  if (!peaks || peaks.length === 0) return;

  // Draw Audio Waveform (Cyan / Silver)
  const barWidth = Math.max(1.5, (w / peaks.length) * state.zoomLevel);
  const halfH = h / 2;

  ctx.fillStyle = '#00d2ff';
  for (let i = 0; i < peaks.length; i++) {
    const x = i * barWidth - state.scrollOffset;
    if (x + barWidth < 0 || x > w) continue;

    const amp = Math.max(0.04, peaks[i]);
    const barHeight = amp * (halfH - 6);

    ctx.fillRect(x, halfH - barHeight, Math.max(1, barWidth - 0.5), barHeight * 2);
  }

  // Draw Detected Silence Overlays (Semi-transparent Studio Red)
  if (state.silenceRegions && state.silenceRegions.length > 0) {
    ctx.fillStyle = 'rgba(229, 9, 20, 0.45)';
    ctx.strokeStyle = '#ff2a2a';
    ctx.lineWidth = 1.5;

    state.silenceRegions.forEach(reg => {
      const startPct = reg.start / totalDuration;
      const endPct = reg.end / totalDuration;

      const sx = startPct * (peaks.length * barWidth) - state.scrollOffset;
      const ex = endPct * (peaks.length * barWidth) - state.scrollOffset;
      const sw = ex - sx;

      if (sx + sw > 0 && sx < w) {
        ctx.fillRect(sx, 2, sw, h - 4);
        ctx.strokeRect(sx, 2, sw, h - 4);
      }
    });
  }

  updatePlayheadLinePosition();
}

function updatePlayheadLinePosition() {
  if (!state.currentMedia || state.currentMedia.duration <= 0) return;
  const totalDuration = state.currentMedia.duration;
  const rect = el.canvasViewport.getBoundingClientRect();
  const barWidth = Math.max(1.5, (rect.width / state.waveformPeaks.length) * state.zoomLevel);
  const totalWaveWidth = state.waveformPeaks.length * barWidth;

  const pct = state.playheadPosition / totalDuration;
  const px = pct * totalWaveWidth - state.scrollOffset;

  el.playheadLine.style.left = `${Math.max(0, Math.min(rect.width, px))}px`;
  el.waveCurrentTime.textContent = formatDurationMs(state.playheadPosition);
}

function formatDurationMs(seconds) {
  if (!seconds || seconds < 0) return '00:00:00.0';
  const totalSec = Math.floor(seconds);
  const ms = Math.floor((seconds - totalSec) * 10);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) {
    return `${pad(h)}:${pad(m)}:${pad(s)}.${ms}`;
  }
  return `${pad(m)}:${pad(s)}.${ms}`;
}

function pad(num) {
  return num < 10 ? '0' + num : num;
}

// --- Silence Analysis ---
async function runSilenceAnalysis() {
  if (!state.currentMedia) {
    alert('Please import an audio or video file first.');
    return;
  }

  const payload = {
    filepath: state.currentMedia.filepath,
    duration: state.currentMedia.duration,
    threshold_db: parseFloat(el.inputThreshold.value),
    min_silence_sec: parseFloat(el.inputMinDuration.value),
    action: el.selectAction.value,
    remaining_silence_sec: parseFloat(el.inputRemainingSilence.value),
    max_silence_sec: el.checkMaxSilence.checked ? parseFloat(el.inputMaxSilence.value) : null
  };

  showStatus('Analyzing audio energy & detecting silent sections...');
  el.btnAnalyze.disabled = true;
  el.btnAnalyze.innerHTML = '<div class="spinner mini"></div> Analyzing...';

  try {
    const data = await api('/api/silence/analyze', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    const analysis = data.analysis;
    state.analysisResult = analysis;
    state.silenceRegions = analysis.regions || [];

    // Update Statistics Banner
    el.statRegions.textContent = Number(analysis.regions_count).toLocaleString();
    el.statTotalSilence.textContent = analysis.total_silence_formatted;
    el.statReduction.textContent = analysis.estimated_reduction_formatted;
    el.statEstimatedOut.textContent = analysis.estimated_output_formatted;
    el.analysisBanner.classList.remove('hidden');

    // Redraw waveform with detected silence regions
    renderWaveform();
    showStatus(`Detected ${analysis.regions_count} silent sections (${analysis.total_silence_formatted} total silence).`);
  } catch (e) {
    alert(`Silence Analysis failed: ${e.message}`);
  } finally {
    el.btnAnalyze.disabled = false;
    el.btnAnalyze.innerHTML = `
      <svg class="btn-icon" viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
      ANALYZE SILENCE
    `;
  }
}

// --- Processing & Truncation ---
async function startProcessing() {
  if (!state.currentMedia) {
    alert('Please import an audio or video file first.');
    return;
  }

  // If analysis hasn't run yet, run it automatically first
  if (state.silenceRegions.length === 0) {
    showStatus('Running pre-process silence analysis...');
    await runSilenceAnalysis();
    if (state.silenceRegions.length === 0) {
      const proceed = confirm('No silent sections were detected at current threshold. Do you still want to process?');
      if (!proceed) return;
    }
  }

  const payload = {
    filepath: state.currentMedia.filepath,
    duration: state.currentMedia.duration,
    silence_regions: state.silenceRegions,
    action: el.selectAction.value,
    remaining_silence_sec: parseFloat(el.inputRemainingSilence.value),
    max_silence_sec: el.checkMaxSilence.checked ? parseFloat(el.inputMaxSilence.value) : null,
    export_format: el.exportFormat.value,
    quality_id: el.exportQuality.value,
    sample_rate: el.exportSamplerate.value,
    channels: el.exportChannels.value === 'original' ? null : parseInt(el.exportChannels.value),
    output_dir: state.settings.export_dir,
    preset_name: el.presetSelect.options[el.presetSelect.selectedIndex]?.text || 'RD Studio'
  };

  showProgressModal(state.currentMedia.filename);

  try {
    const res = await api('/api/silence/process', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    startProgressPolling();
  } catch (e) {
    hideProgressModal();
    alert(`Processing failed to start: ${e.message}`);
  }
}

function showProgressModal(filename) {
  el.progFilename.textContent = filename;
  el.progBarFill.style.width = '0%';
  el.progPct.textContent = '0%';
  el.progStage.textContent = 'Initializing media engine...';
  el.progElapsed.textContent = '00:00';
  el.progRemaining.textContent = 'Estimating...';
  el.progProcessedTime.textContent = '00:00:00';
  el.progressModal.classList.remove('hidden');
}

function hideProgressModal() {
  el.progressModal.classList.add('hidden');
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function startProgressPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);

  state.pollTimer = setInterval(async () => {
    try {
      const data = await api('/api/silence/progress');
      el.progPct.textContent = `${Math.round(data.percentage)}%`;
      el.progBarFill.style.width = `${data.percentage}%`;
      el.progStage.textContent = data.stage || 'Processing...';

      if (data.elapsed_sec) {
        el.progElapsed.textContent = formatDurationSeconds(data.elapsed_sec);
      }
      if (data.remaining_sec) {
        el.progRemaining.textContent = formatDurationSeconds(data.remaining_sec);
      } else {
        el.progRemaining.textContent = 'Calculating...';
      }
      if (data.current_time) {
        el.progProcessedTime.textContent = formatDurationSeconds(data.current_time);
      }

      if (data.status === 'completed') {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        setTimeout(() => {
          hideProgressModal();
          handleProcessingComplete(data.result);
        }, 500);
      } else if (data.status === 'failed') {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        hideProgressModal();
        alert(`Processing Error:\n${data.error || 'Unknown failure.'}`);
      } else if (data.status === 'cancelled') {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        hideProgressModal();
        showStatus('Processing cancelled by user.');
      }
    } catch (e) {
      console.error('Progress poll error:', e);
    }
  }, 350);
}

function handleProcessingComplete(result) {
  state.processedFilePath = result.output_path;
  showStatus(`Processing Complete! Saved to ${result.output_filename} (Reduced by ${result.silence_removed_formatted})`);

  // Load Processed Audio into Preview Player
  audioProcessed.src = `/api/stream/audio?file=${encodeURIComponent(result.output_path)}`;
  audioProcessed.load();

  el.procControls.style.opacity = '1';
  el.procControls.style.pointerEvents = 'auto';
  el.procTimer.textContent = `00:00 / ${result.output_duration_formatted.slice(0, 5)}`;
  el.procSeek.value = 0;

  alert(
    `RD STUDIO — PROCESSING COMPLETE!\n\n` +
    `Output File: ${result.output_filename}\n` +
    `Original Duration: ${result.original_duration_formatted}\n` +
    `New Duration: ${result.output_duration_formatted}\n` +
    `Silence Truncated: ${result.silence_removed_formatted}\n` +
    `Kept Dialogue Segments: ${result.segments_kept}\n\n` +
    `The processed audio is now loaded in the Processed Preview Player below.`
  );
}

function formatDurationSeconds(totalSeconds) {
  if (!totalSeconds || totalSeconds < 0) return '00:00';
  const m = Math.floor(totalSeconds / 60);
  const s = Math.floor(totalSeconds % 60);
  return `${pad(m)}:${pad(s)}`;
}

// --- Audio Preview Players ---
function setupAudioPlayers() {
  // Original Player Events
  el.btnOrigPlay.addEventListener('click', () => {
    if (audioOriginal.paused) {
      audioProcessed.pause();
      audioOriginal.play();
      el.btnOrigPlay.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
    } else {
      audioOriginal.pause();
      el.btnOrigPlay.innerHTML = '<svg class="icon-play" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
    }
  });

  el.btnOrigStop.addEventListener('click', () => {
    audioOriginal.pause();
    audioOriginal.currentTime = 0;
    el.btnOrigPlay.innerHTML = '<svg class="icon-play" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
  });

  audioOriginal.addEventListener('timeupdate', () => {
    if (audioOriginal.duration) {
      const pct = (audioOriginal.currentTime / audioOriginal.duration) * 100;
      el.origSeek.value = pct;
      el.origTimer.textContent = `${formatDurationSeconds(audioOriginal.currentTime)} / ${formatDurationSeconds(audioOriginal.duration)}`;
      state.playheadPosition = audioOriginal.currentTime;
      updatePlayheadLinePosition();
    }
  });

  el.origSeek.addEventListener('input', () => {
    if (audioOriginal.duration) {
      audioOriginal.currentTime = (el.origSeek.value / 100) * audioOriginal.duration;
      state.playheadPosition = audioOriginal.currentTime;
      updatePlayheadLinePosition();
    }
  });

  el.origSpeed.addEventListener('change', () => {
    audioOriginal.playbackRate = parseFloat(el.origSpeed.value);
  });

  el.origVol.addEventListener('input', () => {
    audioOriginal.volume = parseFloat(el.origVol.value);
  });

  // Processed Player Events
  el.btnProcPlay.addEventListener('click', () => {
    if (audioProcessed.paused) {
      audioOriginal.pause();
      audioProcessed.play();
      el.btnProcPlay.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
    } else {
      audioProcessed.pause();
      el.btnProcPlay.innerHTML = '<svg class="icon-play" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
    }
  });

  el.btnProcStop.addEventListener('click', () => {
    audioProcessed.pause();
    audioProcessed.currentTime = 0;
    el.btnProcPlay.innerHTML = '<svg class="icon-play" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
  });

  audioProcessed.addEventListener('timeupdate', () => {
    if (audioProcessed.duration) {
      const pct = (audioProcessed.currentTime / audioProcessed.duration) * 100;
      el.procSeek.value = pct;
      el.procTimer.textContent = `${formatDurationSeconds(audioProcessed.currentTime)} / ${formatDurationSeconds(audioProcessed.duration)}`;
    }
  });

  el.procSeek.addEventListener('input', () => {
    if (audioProcessed.duration) {
      audioProcessed.currentTime = (el.procSeek.value / 100) * audioProcessed.duration;
    }
  });

  el.procSpeed.addEventListener('change', () => {
    audioProcessed.playbackRate = parseFloat(el.procSpeed.value);
  });

  el.procVol.addEventListener('input', () => {
    audioProcessed.volume = parseFloat(el.procVol.value);
  });
}

// --- Batch Queue Management ---
async function updateBatchBadge() {
  try {
    const data = await api('/api/batch/items');
    const items = data.items || [];
    el.batchCounter.textContent = items.length;
    el.batchCounter.classList.toggle('hidden', items.length === 0);
  } catch (e) {}
}

async function renderBatchModal() {
  try {
    const data = await api('/api/batch/items');
    const items = data.items || [];
    el.batchTableBody.innerHTML = '';

    if (items.length === 0) {
      el.batchTableBody.innerHTML = '<tr><td colspan="7" class="empty-table-msg">No files in batch queue. Click "+ Add Media Files".</td></tr>';
      return;
    }

    items.forEach(it => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td title="${it.filepath}"><strong>${it.filename}</strong></td>
        <td>${it.is_video ? 'Video' : 'Audio'}</td>
        <td class="mono">${it.duration_formatted}</td>
        <td><span class="status-pill status-${it.status}">${it.status}</span></td>
        <td>${it.stage} ${it.progress > 0 && it.progress < 100 ? `(${Math.round(it.progress)}%)` : ''}</td>
        <td class="mono">${it.output_duration_formatted ? it.output_duration_formatted : '-'}</td>
        <td>
          <button class="btn-subtle" onclick="removeBatchItem('${it.id}')">Remove</button>
        </td>
      `;
      el.batchTableBody.appendChild(tr);
    });

    if (data.is_running && !state.batchPollTimer) {
      state.batchPollTimer = setInterval(renderBatchModal, 600);
    } else if (!data.is_running && state.batchPollTimer) {
      clearInterval(state.batchPollTimer);
      state.batchPollTimer = null;
    }
  } catch (e) {
    console.error('Failed to render batch modal:', e);
  }
}

window.removeBatchItem = async function(id) {
  await api('/api/batch/remove', { method: 'POST', body: JSON.stringify({ id }) });
  renderBatchModal();
  updateBatchBadge();
};

async function startBatchProcessAll() {
  const p = state.presets.find(item => item.id === state.activePresetId) || state.presets[0];
  const payload = {
    settings: {
      threshold_db: parseFloat(el.inputThreshold.value),
      min_silence_sec: parseFloat(el.inputMinDuration.value),
      action: el.selectAction.value,
      remaining_silence_sec: parseFloat(el.inputRemainingSilence.value),
      max_silence_sec: el.checkMaxSilence.checked ? parseFloat(el.inputMaxSilence.value) : null,
      export_format: el.exportFormat.value,
      quality_id: el.exportQuality.value,
      sample_rate: el.exportSamplerate.value,
      channels: el.exportChannels.value === 'original' ? null : parseInt(el.exportChannels.value),
      preset_name: p.name
    },
    output_dir: state.settings.export_dir
  };

  try {
    await api('/api/batch/process_all', { method: 'POST', body: JSON.stringify(payload) });
    renderBatchModal();
  } catch (e) {
    alert(`Could not start batch: ${e.message}`);
  }
}

// --- History Log ---
async function renderHistoryModal() {
  try {
    const data = await api('/api/history');
    const records = data.history || [];
    el.historyTableBody.innerHTML = '';

    if (records.length === 0) {
      el.historyTableBody.innerHTML = '<tr><td colspan="7" class="empty-table-msg">No history records yet.</td></tr>';
      return;
    }

    records.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="mono">${r.timestamp || '-'}</td>
        <td title="${r.output_path || ''}"><strong>${r.filename}</strong></td>
        <td>${r.preset || 'Default'}</td>
        <td class="mono">${r.original_duration || '-'}</td>
        <td class="mono text-green">${r.output_duration || '-'}</td>
        <td class="mono text-red">${r.silence_removed || '-'}</td>
        <td><span class="status-pill status-completed">${r.status}</span></td>
      `;
      el.historyTableBody.appendChild(tr);
    });
  } catch (e) {
    console.error('Failed to load history:', e);
  }
}

// --- Presets Manager ---
function renderPresetsManager() {
  el.presetsManagerList.innerHTML = '';
  state.presets.forEach(p => {
    const card = document.createElement('div');
    card.className = `preset-card-item ${p.id === state.activePresetId ? 'active' : ''}`;
    card.innerHTML = `
      <div class="preset-item-info">
        <span class="preset-item-name">${p.name} ${p.is_builtin ? '<small>(Factory)</small>' : ''}</span>
        <span class="preset-item-desc">${p.description || ''}</span>
        <span class="preset-item-meta mono">Threshold: ${p.threshold_db} dB | Min: ${p.min_silence_sec}s | Remaining: ${p.remaining_silence_sec}s</span>
      </div>
      <div class="preset-item-actions">
        <button class="btn-subtle" onclick="activatePresetFromModal('${p.id}')">Select</button>
        ${!p.is_builtin ? `<button class="btn-subtle text-red" onclick="deletePresetFromModal('${p.id}')">Delete</button>` : ''}
      </div>
    `;
    el.presetsManagerList.appendChild(card);
  });
}

window.activatePresetFromModal = function(id) {
  selectPreset(id);
  el.presetsModal.classList.add('hidden');
};

window.deletePresetFromModal = async function(id) {
  if (!confirm('Are you sure you want to delete this custom preset?')) return;
  try {
    await api(`/api/presets/${id}`, { method: 'DELETE' });
    await loadPresets();
  } catch (e) {
    alert(e.message);
  }
};

// --- Event Listeners Setup ---
function setupEventListeners() {
  setupAudioPlayers();

  // Native File Dialog or Fallback
  el.btnBrowse.addEventListener('click', async () => {
    try {
      const data = await api('/api/dialog/browse', { method: 'POST' });
      if (data.media_info) {
        setLoadedMedia(data.media_info);
      } else if (!data.cancelled) {
        el.fileInputFallback.click();
      }
    } catch (e) {
      el.fileInputFallback.click();
    }
  });

  el.fileInputFallback.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  });

  // Drag & Drop
  el.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    el.dropZone.classList.add('drag-over');
  });

  el.dropZone.addEventListener('dragleave', () => {
    el.dropZone.classList.remove('drag-over');
  });

  el.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    el.dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  el.btnClearMedia.addEventListener('click', clearMedia);

  // Threshold Sync
  el.sliderThreshold.addEventListener('input', () => {
    el.inputThreshold.value = parseFloat(el.sliderThreshold.value).toFixed(2);
  });

  el.inputThreshold.addEventListener('change', () => {
    let val = parseFloat(el.inputThreshold.value);
    if (isNaN(val)) val = -20.0;
    val = Math.max(-80, Math.min(0, val));
    el.inputThreshold.value = val.toFixed(2);
    el.sliderThreshold.value = val;
  });

  // Min Silence Duration & Chips
  el.inputMinDuration.addEventListener('input', updateActiveChips);
  el.inputRemainingSilence.addEventListener('input', updateActiveChips);

  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const targetId = chip.getAttribute('data-target');
      const val = chip.getAttribute('data-val');
      const targetInput = document.getElementById(targetId);
      if (targetInput) {
        targetInput.value = val;
        updateActiveChips();
      }
    });
  });

  // Action Change
  el.selectAction.addEventListener('change', updateActionVisibility);

  // Max Silence Checkbox
  el.checkMaxSilence.addEventListener('change', () => {
    if (el.checkMaxSilence.checked) {
      el.maxSilenceInputContainer.style.opacity = '1';
      el.maxSilenceInputContainer.style.pointerEvents = 'auto';
    } else {
      el.maxSilenceInputContainer.style.opacity = '0.4';
      el.maxSilenceInputContainer.style.pointerEvents = 'none';
    }
  });

  // Preset Selector
  el.presetSelect.addEventListener('change', () => {
    selectPreset(el.presetSelect.value);
  });

  // Save Preset Prompt
  el.btnSavePresetPrompt.addEventListener('click', () => {
    el.customPresetName.value = '';
    el.savePresetModal.classList.remove('hidden');
  });

  el.btnConfirmSavePreset.addEventListener('click', async () => {
    const name = el.customPresetName.value.trim();
    if (!name) {
      alert('Please enter a preset name.');
      return;
    }

    const payload = {
      name,
      threshold_db: parseFloat(el.inputThreshold.value),
      min_silence_sec: parseFloat(el.inputMinDuration.value),
      action: el.selectAction.value,
      remaining_silence_sec: parseFloat(el.inputRemainingSilence.value),
      max_silence_sec: el.checkMaxSilence.checked ? parseFloat(el.inputMaxSilence.value) : null
    };

    try {
      const res = await api('/api/presets', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      el.savePresetModal.classList.add('hidden');
      await loadPresets();
      selectPreset(res.preset.id);
      showStatus(`Saved custom preset "${name}"`);
    } catch (e) {
      alert(`Failed to save preset: ${e.message}`);
    }
  });

  // Export Format Change
  el.exportFormat.addEventListener('change', updateExportQualityOptions);

  // Change Export Folder
  el.btnChangeFolder.addEventListener('click', async () => {
    try {
      const res = await api('/api/dialog/browse_folder', { method: 'POST' });
      if (!res.cancelled && res.directory) {
        state.settings.export_dir = res.directory;
        el.exportTargetDisplay.textContent = res.directory;
        el.exportTargetDisplay.title = res.directory;
        await api('/api/settings', {
          method: 'POST',
          body: JSON.stringify(state.settings)
        });
      }
    } catch (e) {}
  });

  // Execution Buttons
  el.btnAnalyze.addEventListener('click', runSilenceAnalysis);
  el.btnProcess.addEventListener('click', startProcessing);

  el.btnCancelProcess.addEventListener('click', async () => {
    if (confirm('Cancel active silence removal job?')) {
      await api('/api/silence/cancel', { method: 'POST' });
    }
  });

  // Waveform Zoom & Navigation
  el.btnZoomIn.addEventListener('click', () => {
    state.zoomLevel = Math.min(16.0, state.zoomLevel * 1.5);
    el.zoomLevelDisplay.textContent = `${state.zoomLevel.toFixed(1)}x`;
    renderWaveform();
  });

  el.btnZoomOut.addEventListener('click', () => {
    state.zoomLevel = Math.max(1.0, state.zoomLevel / 1.5);
    if (state.zoomLevel <= 1.0) state.scrollOffset = 0;
    el.zoomLevelDisplay.textContent = `${state.zoomLevel.toFixed(1)}x`;
    renderWaveform();
  });

  el.btnZoomReset.addEventListener('click', () => {
    state.zoomLevel = 1.0;
    state.scrollOffset = 0;
    el.zoomLevelDisplay.textContent = '1x';
    renderWaveform();
  });

  // Waveform Scrubbing / Clicking
  el.canvasViewport.addEventListener('click', (e) => {
    if (!state.currentMedia || state.currentMedia.duration <= 0) return;
    const rect = el.canvasViewport.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const barWidth = Math.max(1.5, (rect.width / state.waveformPeaks.length) * state.zoomLevel);
    const totalWaveWidth = state.waveformPeaks.length * barWidth;

    const targetX = clickX + state.scrollOffset;
    const targetPct = Math.max(0, Math.min(1, targetX / totalWaveWidth));
    const targetSec = targetPct * state.currentMedia.duration;

    state.playheadPosition = targetSec;
    audioOriginal.currentTime = targetSec;
    updatePlayheadLinePosition();
  });

  // Navigation Modals
  el.btnBatchToggle.addEventListener('click', () => {
    renderBatchModal();
    el.batchModal.classList.remove('hidden');
  });

  el.btnAddBatch.addEventListener('click', async () => {
    if (!state.currentMedia) return;
    await api('/api/batch/add', {
      method: 'POST',
      body: JSON.stringify({ filepath: state.currentMedia.filepath })
    });
    updateBatchBadge();
    showStatus(`Added ${state.currentMedia.filename} to batch queue.`);
  });

  el.btnBatchAddFiles.addEventListener('click', async () => {
    const data = await api('/api/dialog/browse', { method: 'POST' });
    if (data.media_info) {
      await api('/api/batch/add', {
        method: 'POST',
        body: JSON.stringify({ filepath: data.media_info.filepath })
      });
      renderBatchModal();
      updateBatchBadge();
    }
  });

  el.btnBatchClear.addEventListener('click', async () => {
    if (confirm('Clear all files from batch queue?')) {
      await api('/api/batch/clear', { method: 'POST' });
      renderBatchModal();
      updateBatchBadge();
    }
  });

  el.btnBatchProcessAll.addEventListener('click', startBatchProcessAll);

  el.btnPresetsModal.addEventListener('click', () => {
    renderPresetsManager();
    el.presetsModal.classList.remove('hidden');
  });

  el.btnHistoryModal.addEventListener('click', () => {
    renderHistoryModal();
    el.historyModal.classList.remove('hidden');
  });

  el.btnClearHistory.addEventListener('click', async () => {
    if (confirm('Clear all processing history?')) {
      await api('/api/history/clear', { method: 'POST' });
      renderHistoryModal();
    }
  });

  el.btnSettingsModal.addEventListener('click', () => {
    el.settingsModal.classList.remove('hidden');
  });

  el.btnBrowseSettingExport.addEventListener('click', async () => {
    const res = await api('/api/dialog/browse_folder', { method: 'POST' });
    if (!res.cancelled && res.directory) {
      el.settingExportDir.value = res.directory;
    }
  });

  el.btnSaveSettings.addEventListener('click', async () => {
    const updated = {
      export_dir: el.settingExportDir.value,
      temp_dir: el.settingTempDir.value,
      auto_clean_temp: el.settingAutoClean.checked,
      confirm_overwrite: el.settingConfirmOverwrite.checked
    };
    await api('/api/settings', {
      method: 'POST',
      body: JSON.stringify(updated)
    });
    state.settings = updated;
    el.exportTargetDisplay.textContent = updated.export_dir;
    el.settingsModal.classList.add('hidden');
    showStatus('Preferences saved successfully.');
  });

  el.btnAboutModal.addEventListener('click', () => {
    el.aboutModal.classList.remove('hidden');
  });

  // Modal Close Buttons
  document.querySelectorAll('.btn-close-modal, [data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-close');
      if (targetId) {
        document.getElementById(targetId)?.classList.add('hidden');
      }
    });
  });
}
