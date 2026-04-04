#!/usr/bin/env python3
"""
fal_queue_image_run.py — fal.ai queue-based image generation with cost tracking

Submits an image generation job to fal.ai, polls for result, downloads output,
and logs billing info from response headers.

Requires: FAL_KEY in env or ~/.env
Dependencies: pip install requests python-dotenv Pillow

Usage:
    python3 fal_queue_image_run.py \\
        --model fal-ai/nano-banana-2 \\
        --prompt "pixel art warrior, game sprite, transparent background" \\
        --output public/assets/warrior.png

    python3 fal_queue_image_run.py \\
        --model fal-ai/gpt-image-1 \\
        --prompt "medieval castle, concept art" \\
        --size landscape_4_3 \\
        --output public/assets/castle.png \\
        --chroma-key  # remove #00FF00 background after generation
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── Env loading ──────────────────────────────────────────────────────────────

def load_env():
    """Load ~/.env file into os.environ (without requiring python-dotenv)."""
    env_path = Path.home() / '.env'
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        eq = line.find('=')
        if eq == -1:
            continue
        key = line[:eq].strip()
        val = line[eq + 1:].strip().strip('"\'')
        if key not in os.environ:
            os.environ[key] = val

load_env()

FAL_KEY = os.environ.get('FAL_KEY')
if not FAL_KEY:
    print('Error: FAL_KEY not found in env or ~/.env', file=sys.stderr)
    print('Get your key at fal.ai', file=sys.stderr)
    sys.exit(1)

POLL_INTERVAL = 3  # seconds
MAX_POLLS = 200    # 10 minutes

# ── HTTP helpers ─────────────────────────────────────────────────────────────

def fal_request(method: str, url: str, body: dict | None = None) -> tuple[dict, dict]:
    """Make a fal.ai request. Returns (response_json, headers)."""
    data = json.dumps(body).encode() if body else None
    headers = {
        'Authorization': f'Key {FAL_KEY}',
        'Content-Type': 'application/json',
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_headers = dict(resp.headers)
            resp_body = json.loads(resp.read())
            return resp_body, resp_headers
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise RuntimeError(f'fal.ai {e.code}: {body_text}') from e


def download_file(url: str, output_path: Path) -> None:
    """Download a file from URL to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        output_path.write_bytes(resp.read())
    size = output_path.stat().st_size
    if size == 0:
        raise RuntimeError(f'Downloaded file is empty: {output_path}')
    print(f'Downloaded {size / 1024:.1f}KB -> {output_path}')


# ── Chroma-key removal ───────────────────────────────────────────────────────

def remove_chroma_key(image_path: Path, tolerance: int = 60) -> None:
    """Remove #00FF00 green background, convert to RGBA PNG."""
    try:
        from PIL import Image
        import struct
    except ImportError:
        print('Warning: Pillow not installed. Skipping chroma-key removal.', file=sys.stderr)
        print('Install: pip install Pillow', file=sys.stderr)
        return

    img = Image.open(image_path).convert('RGBA')
    pixels = img.load()
    w, h = img.size

    removed = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            # Match green: low red, high green, low blue
            if r < tolerance and g > (255 - tolerance) and b < tolerance:
                pixels[x, y] = (0, 0, 0, 0)
                removed += 1

    img.save(image_path, 'PNG')
    pct = removed / (w * h) * 100
    print(f'Chroma-key: removed {removed} green pixels ({pct:.1f}% of image)')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='fal.ai queue-based image generation')
    parser.add_argument('--model', default='fal-ai/nano-banana-2',
                        help='Model endpoint (default: fal-ai/nano-banana-2)')
    parser.add_argument('--prompt', required=True, help='Image generation prompt')
    parser.add_argument('--negative-prompt', default='', help='Negative prompt')
    parser.add_argument('--output', required=True, help='Output file path')
    parser.add_argument('--size', default='square',
                        help='Image size: square | landscape_4_3 | portrait_16_9 | 1024x1024')
    parser.add_argument('--num-images', type=int, default=1)
    parser.add_argument('--seed', type=int, help='Random seed for reproducibility')
    parser.add_argument('--steps', type=int, help='Inference steps (model-dependent)')
    parser.add_argument('--chroma-key', action='store_true',
                        help='Remove #00FF00 background after generation')
    parser.add_argument('--chroma-tolerance', type=int, default=60,
                        help='Green detection tolerance (0-255, default 60)')
    args = parser.parse_args()

    output_path = Path(args.output)

    # Build request body
    body: dict = {
        'prompt': args.prompt,
        'image_size': args.size,
        'num_images': args.num_images,
    }
    if args.negative_prompt:
        body['negative_prompt'] = args.negative_prompt
    if args.seed is not None:
        body['seed'] = args.seed
    if args.steps is not None:
        body['num_inference_steps'] = args.steps

    # Submit to queue
    queue_url = f'https://queue.fal.run/{args.model}'
    print(f'[fal.ai] Submitting to {args.model}...')
    print(f'[fal.ai] Prompt: {args.prompt[:80]}{"..." if len(args.prompt) > 80 else ""}')

    result, headers = fal_request('POST', queue_url, body)
    request_id = result.get('request_id')
    if not request_id:
        raise RuntimeError(f'No request_id in response: {result}')
    print(f'[fal.ai] Request ID: {request_id}')

    # Poll for result
    status_url = f'https://queue.fal.run/{args.model}/requests/{request_id}'
    for i in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        data, resp_headers = fal_request('GET', status_url)
        status = data.get('status', 'UNKNOWN')
        print(f'\r[fal.ai] {status} ({i * POLL_INTERVAL}s)...', end='', flush=True)

        if status == 'COMPLETED':
            print()  # newline after status
            # Log billing info
            credits = resp_headers.get('x-fal-credits-used') or resp_headers.get('X-Fal-Credits-Used')
            units = resp_headers.get('x-fal-billing-units') or resp_headers.get('X-Fal-Billing-Units')
            if credits:
                print(f'[fal.ai] Cost: ${float(credits):.4f} ({units or "?"} units)')

            # Get image URL from output
            output = data.get('output', {})
            images = output.get('images', [])
            if not images:
                raise RuntimeError(f'No images in output: {data}')
            image_url = images[0]['url']

            # Download
            download_file(image_url, output_path)

            # Optional: chroma-key removal
            if args.chroma_key:
                print('[fal.ai] Removing chroma-key background...')
                remove_chroma_key(output_path, args.chroma_tolerance)

            # Save .meta.json
            meta = {
                'prompt': args.prompt,
                'model': args.model,
                'request_id': request_id,
                'image_size': args.size,
                'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'source': 'fal-ai',
                'output_path': str(output_path),
                'credits_used': float(credits) if credits else None,
                'seed': args.seed,
                'chroma_key_applied': args.chroma_key,
            }
            meta_path = output_path.with_suffix('.meta.json')
            meta_path.write_text(json.dumps(meta, indent=2))
            print(f'Meta -> {meta_path}')
            print(f'\nDone: {output_path}')
            return

        if status == 'FAILED':
            print()
            error = data.get('error') or data.get('detail', 'Unknown error')
            raise RuntimeError(f'Generation failed: {error}')

    raise RuntimeError(f'Timed out after {MAX_POLLS * POLL_INTERVAL}s')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nCancelled.')
        sys.exit(1)
    except RuntimeError as e:
        print(f'\nError: {e}', file=sys.stderr)
        sys.exit(1)
