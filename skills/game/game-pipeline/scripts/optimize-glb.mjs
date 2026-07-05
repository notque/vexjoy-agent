#!/usr/bin/env node
/**
 * optimize-glb.mjs — GLB post-processing via @gltf-transform/cli
 *
 * Reduces GLB file size 80-95% via:
 *   - Texture resize to 1024x1024 max
 *   - WebP conversion
 *   - Meshopt compression (quantization + filter)
 *   - Dedup and prune
 *
 * Requires: npm install -g @gltf-transform/cli
 *
 * Usage:
 *   node optimize-glb.mjs input.glb output.glb
 *   node optimize-glb.mjs input.glb  (overwrites in place)
 */

import { execSync } from 'child_process';
import { existsSync, statSync, renameSync, copyFileSync } from 'fs';
import { basename, dirname, join } from 'path';

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

function checkGltfTransform() {
  try {
    execSync('gltf-transform --version', { stdio: 'pipe' });
  } catch {
    console.error('Error: @gltf-transform/cli not found.');
    console.error('Install: npm install -g @gltf-transform/cli');
    process.exit(1);
  }
}

function optimize(inputPath, outputPath) {
  if (!existsSync(inputPath)) {
    throw new Error(`Input file not found: ${inputPath}`);
  }

  const inputSize = statSync(inputPath).size;
  const tmpPath = outputPath + '.tmp.glb';

  console.log(`Input:  ${inputPath} (${formatBytes(inputSize)})`);

  // Step 1: Dedup + prune (removes duplicate meshes, unused nodes)
  console.log('[1/4] Deduplicating and pruning...');
  execSync(`gltf-transform dedup "${inputPath}" "${tmpPath}"`, { stdio: 'inherit' });
  execSync(`gltf-transform prune "${tmpPath}" "${tmpPath}"`, { stdio: 'inherit' });

  // Step 2: Resize textures to 1024x1024 max
  console.log('[2/4] Resizing textures...');
  execSync(`gltf-transform resize "${tmpPath}" "${tmpPath}" --width 1024 --height 1024`, {
    stdio: 'inherit',
  });

  // Step 3: Convert textures to WebP
  console.log('[3/4] Converting textures to WebP...');
  try {
    execSync(`gltf-transform webp "${tmpPath}" "${tmpPath}"`, { stdio: 'inherit' });
  } catch {
    console.warn('Warning: WebP conversion failed (sharp may not be installed). Skipping.');
    console.warn('Install sharp for WebP support: npm install -g sharp');
  }

  // Step 4: Meshopt compression (quantization + vertex cache optimization)
  console.log('[4/4] Applying meshopt compression...');
  execSync(`gltf-transform meshopt "${tmpPath}" "${outputPath}"`, { stdio: 'inherit' });

  // Cleanup temp
  try { execSync(`rm -f "${tmpPath}"`); } catch {}

  if (!existsSync(outputPath)) {
    throw new Error(`Output not created: ${outputPath}`);
  }

  const outputSize = statSync(outputPath).size;
  const reduction = ((1 - outputSize / inputSize) * 100).toFixed(1);
  console.log(`\nOutput: ${outputPath} (${formatBytes(outputSize)})`);
  console.log(`Reduction: ${reduction}% (${formatBytes(inputSize)} -> ${formatBytes(outputSize)})`);
}

// ── Main ──────────────────────────────────────────────────────────────────────

const [,, inputArg, outputArg] = process.argv;

if (!inputArg) {
  console.error('Usage: node optimize-glb.mjs <input.glb> [output.glb]');
  process.exit(1);
}

const inputPath = inputArg;
const outputPath = outputArg || inputArg; // overwrite in place if no output specified

// If overwriting in place, use a temp output
const actualOutput = outputPath === inputPath
  ? inputPath.replace(/\.glb$/, '-optimized.glb')
  : outputPath;

checkGltfTransform();

try {
  optimize(inputPath, actualOutput);
  if (actualOutput !== outputPath && outputPath === inputPath) {
    // Overwrite original with optimized
    renameSync(actualOutput, inputPath);
    console.log(`Replaced original: ${inputPath}`);
  }
} catch (err) {
  console.error(`\nOptimization failed: ${err.message}`);
  process.exit(1);
}
