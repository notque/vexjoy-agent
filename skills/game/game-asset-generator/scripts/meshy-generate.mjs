#!/usr/bin/env node
/**
 * meshy-generate.mjs — Meshy AI 3D model generation pipeline
 *
 * Modes:
 *   text-to-3d  <prompt> [--style realistic|cartoon|low-poly]
 *   image-to-3d <image-path-or-url>
 *   rig         <task-id>
 *   animate     <rig-task-id> [--preset walk|run|idle|jump|dance]
 *   status      <task-id>
 *
 * Requires: MESHY_API_KEY in env or ~/.env
 *
 * Usage:
 *   node meshy-generate.mjs text-to-3d "a fantasy warrior" --output public/assets/warrior.glb
 *   node meshy-generate.mjs status abc123
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { createWriteStream } from 'fs';
import { pipeline } from 'stream/promises';
import { join, dirname, basename } from 'path';
import { homedir } from 'os';

// ── Env loading ─────────────────────────────────────────────────────────────

function loadEnv() {
  const envPath = join(homedir(), '.env');
  if (!existsSync(envPath)) return;
  const lines = readFileSync(envPath, 'utf8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
    if (!process.env[key]) process.env[key] = val;
  }
}

loadEnv();

const API_KEY = process.env.MESHY_API_KEY;
const BASE_URL = 'https://api.meshy.ai';
const POLL_INTERVAL_MS = 5000;
const MAX_POLL_ATTEMPTS = 120; // 10 minutes

if (!API_KEY) {
  console.error('Error: MESHY_API_KEY not found in env or ~/.env');
  console.error('Get your key at app.meshy.ai');
  process.exit(1);
}

// ── HTTP helpers ─────────────────────────────────────────────────────────────

async function meshyPost(path, body) {
  const resp = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Meshy API ${resp.status}: ${text}`);
  }
  return resp.json();
}

async function meshyGet(path) {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Authorization': `Bearer ${API_KEY}` },
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Meshy API ${resp.status}: ${text}`);
  }
  return resp.json();
}

// ── Polling ───────────────────────────────────────────────────────────────────

async function pollTask(endpoint, taskId) {
  for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
    const data = await meshyGet(`${endpoint}/${taskId}`);
    const status = data.status;
    process.stderr.write(`\r[meshy] ${taskId} — ${status} (${i * POLL_INTERVAL_MS / 1000}s)`);

    if (status === 'SUCCEEDED') {
      process.stderr.write('\n');
      return data;
    }
    if (status === 'FAILED') {
      process.stderr.write('\n');
      throw new Error(`Task failed: ${JSON.stringify(data.task_error)}`);
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
  }
  throw new Error(`Task timed out after ${MAX_POLL_ATTEMPTS * POLL_INTERVAL_MS / 1000}s`);
}

// ── Download ──────────────────────────────────────────────────────────────────

async function downloadFile(url, outputPath) {
  mkdirSync(dirname(outputPath), { recursive: true });
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);
  const dest = createWriteStream(outputPath);
  await pipeline(resp.body, dest);
  const size = existsSync(outputPath) ? readFileSync(outputPath).length : 0;
  if (size === 0) throw new Error(`Downloaded file is empty: ${outputPath}`);
  console.log(`Downloaded ${(size / 1024).toFixed(1)}KB -> ${outputPath}`);
}

function saveMeta(outputPath, meta) {
  const metaPath = outputPath.replace(/\.glb$/, '.meta.json');
  writeFileSync(metaPath, JSON.stringify(meta, null, 2));
  console.log(`Meta -> ${metaPath}`);
}

// ── Commands ──────────────────────────────────────────────────────────────────

async function cmdTextTo3D(args) {
  const prompt = args[0];
  if (!prompt) throw new Error('Usage: text-to-3d <prompt>');

  const styleArg = args.indexOf('--style');
  const style = styleArg !== -1 ? args[styleArg + 1] : 'realistic';
  const outputArg = args.indexOf('--output');
  const outputPath = outputArg !== -1 ? args[outputArg + 1] : `output-${Date.now()}.glb`;

  console.log(`[meshy] Submitting preview: "${prompt}"`);
  const preview = await meshyPost('/openapi/v2/3d-model-preview', {
    object_prompt: prompt,
    style_prompt: 'game-ready, PBR textures, clean geometry',
    art_style: style,
    should_remesh: true,
  });
  const previewId = preview.result;
  console.log(`[meshy] Preview task: ${previewId}`);

  const previewData = await pollTask('/openapi/v2/3d-model-preview', previewId);

  console.log(`[meshy] Submitting refine...`);
  const refine = await meshyPost('/openapi/v2/3d-model', {
    preview_task_id: previewId,
    enable_pbr: true,
    texture_richness: 'high',
  });
  const refineId = refine.result;
  console.log(`[meshy] Refine task: ${refineId}`);

  const refineData = await pollTask('/openapi/v2/3d-model', refineId);
  const glbUrl = refineData.model_urls?.glb;
  if (!glbUrl) throw new Error('No GLB URL in refine result');

  await downloadFile(glbUrl, outputPath);
  saveMeta(outputPath, {
    prompt,
    style,
    preview_task_id: previewId,
    refine_task_id: refineId,
    generated_at: new Date().toISOString(),
    source: 'meshyai',
    original_url: glbUrl,
    expires_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
  });
  return outputPath;
}

async function cmdImageTo3D(args) {
  const imagePath = args[0];
  if (!imagePath) throw new Error('Usage: image-to-3d <image-path-or-url>');
  const outputArg = args.indexOf('--output');
  const outputPath = outputArg !== -1 ? args[outputArg + 1] : `output-${Date.now()}.glb`;

  let imageUrl = imagePath;
  if (!imagePath.startsWith('http')) {
    // Local file — base64 encode
    const ext = imagePath.split('.').pop().toLowerCase();
    const mime = ext === 'png' ? 'image/png' : 'image/jpeg';
    const b64 = readFileSync(imagePath).toString('base64');
    imageUrl = `data:${mime};base64,${b64}`;
    console.log(`[meshy] Encoding local file as base64 (${(b64.length / 1024).toFixed(0)}KB)`);
  }

  console.log(`[meshy] Submitting image-to-3D...`);
  const task = await meshyPost('/openapi/v2/image-to-3d', {
    image_url: imageUrl,
    enable_pbr: true,
    should_remesh: true,
  });
  const taskId = task.result;
  console.log(`[meshy] Task: ${taskId}`);

  const data = await pollTask('/openapi/v2/image-to-3d', taskId);
  const glbUrl = data.model_urls?.glb;
  if (!glbUrl) throw new Error('No GLB URL in result');

  await downloadFile(glbUrl, outputPath);
  saveMeta(outputPath, {
    image_source: imagePath,
    task_id: taskId,
    generated_at: new Date().toISOString(),
    source: 'meshyai-image-to-3d',
    original_url: glbUrl,
    expires_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
  });
  return outputPath;
}

async function cmdRig(args) {
  const taskId = args[0];
  if (!taskId) throw new Error('Usage: rig <refine-task-id>');
  const outputArg = args.indexOf('--output');
  const outputPath = outputArg !== -1 ? args[outputArg + 1] : `rigged-${taskId}.glb`;

  console.log(`[meshy] Submitting rig for task ${taskId}...`);
  const rig = await meshyPost(`/openapi/v1/3d-model/${taskId}/rig`, {
    skeleton_type: 'humanoid',
  });
  const rigId = rig.result;
  console.log(`[meshy] Rig task: ${rigId}`);

  const data = await pollTask('/openapi/v1/3d-model-rig', rigId);
  const glbUrl = data.model_urls?.glb;
  if (!glbUrl) throw new Error('No GLB URL in rig result');

  await downloadFile(glbUrl, outputPath);
  saveMeta(outputPath, {
    source_task_id: taskId,
    rig_task_id: rigId,
    generated_at: new Date().toISOString(),
    source: 'meshyai-rig',
    original_url: glbUrl,
  });
  return outputPath;
}

async function cmdAnimate(args) {
  const rigTaskId = args[0];
  if (!rigTaskId) throw new Error('Usage: animate <rig-task-id> [--preset walk|run|idle]');
  const presetArg = args.indexOf('--preset');
  const preset = presetArg !== -1 ? args[presetArg + 1] : 'walk';
  const outputArg = args.indexOf('--output');
  const outputPath = outputArg !== -1 ? args[outputArg + 1] : `animated-${rigTaskId}-${preset}.glb`;

  console.log(`[meshy] Submitting animate (${preset}) for rig ${rigTaskId}...`);
  const anim = await meshyPost(`/openapi/v1/3d-model/${rigTaskId}/animate`, {
    animation_preset: preset,
  });
  const animId = anim.result;
  console.log(`[meshy] Animate task: ${animId}`);

  const data = await pollTask('/openapi/v1/3d-model-animation', animId);
  const glbUrl = data.model_urls?.glb;
  if (!glbUrl) throw new Error('No GLB URL in animate result');

  await downloadFile(glbUrl, outputPath);
  saveMeta(outputPath, {
    rig_task_id: rigTaskId,
    anim_task_id: animId,
    animation_preset: preset,
    generated_at: new Date().toISOString(),
    source: 'meshyai-animate',
    original_url: glbUrl,
  });
  return outputPath;
}

async function cmdStatus(args) {
  const taskId = args[0];
  if (!taskId) throw new Error('Usage: status <task-id>');

  // Try all endpoint types
  const endpoints = [
    '/openapi/v2/3d-model',
    '/openapi/v2/3d-model-preview',
    '/openapi/v2/image-to-3d',
    '/openapi/v1/3d-model-rig',
    '/openapi/v1/3d-model-animation',
  ];

  for (const ep of endpoints) {
    try {
      const data = await meshyGet(`${ep}/${taskId}`);
      console.log(`Endpoint: ${ep}`);
      console.log(JSON.stringify(data, null, 2));
      return;
    } catch (e) {
      // Try next endpoint
    }
  }
  throw new Error(`Task ${taskId} not found on any endpoint`);
}

// ── Main ──────────────────────────────────────────────────────────────────────

const [,, mode, ...rest] = process.argv;

const commands = {
  'text-to-3d': cmdTextTo3D,
  'image-to-3d': cmdImageTo3D,
  'rig': cmdRig,
  'animate': cmdAnimate,
  'status': cmdStatus,
};

if (!mode || !commands[mode]) {
  console.error('Usage: node meshy-generate.mjs <mode> [args]');
  console.error('Modes: text-to-3d | image-to-3d | rig | animate | status');
  process.exit(1);
}

commands[mode](rest).then((result) => {
  if (result) console.log(`\nDone: ${result}`);
}).catch((err) => {
  console.error(`\nError: ${err.message}`);
  process.exit(1);
});
