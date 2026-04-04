# Deploy Reference

Game deployment options. The game output is always static HTML+JS+assets — it works on any static host.

---

## Pre-Deploy Checklist

Run before every deployment. These catches prevent the most common deploy failures.

```bash
#!/bin/bash
# pre-deploy-check.sh

set -e
echo "=== Pre-Deploy Checks ==="

# 1. Build must succeed
npm run build
echo "OK: build succeeded"

# 2. All expected assets in dist/
if [ ! -d "dist" ] || [ -z "$(ls -A dist/)" ]; then
  echo "FAIL: dist/ is empty or missing"
  exit 1
fi
echo "OK: dist/ populated ($(ls dist/ | wc -l) items)"

# 3. No localhost references
if grep -r "localhost" dist/ --include="*.js" --include="*.html" -l 2>/dev/null; then
  echo "WARN: localhost references found in dist/ — game may not work in production"
fi

# 4. No file:// references (breaks hosted games)
if grep -r "file://" dist/ --include="*.js" --include="*.html" -l 2>/dev/null; then
  echo "FAIL: file:// references found — will break on any host"
  exit 1
fi

# 5. Check for absolute asset paths (common mistake)
if grep -rP 'src=["'"'"']/' dist/ --include="*.html" -l 2>/dev/null; then
  echo "WARN: absolute src paths found — may break on subdirectory deploys"
fi

echo "=== Pre-deploy checks passed ==="
```

---

## GitHub Pages

**Requirements**: Public repo or GitHub Pro. Custom domain optional.

```bash
# One-time setup
npm install --save-dev gh-pages

# package.json
{
  "scripts": {
    "deploy": "npm run build && npx gh-pages -d dist"
  },
  "homepage": "https://{username}.github.io/{repo-name}"
}

# Deploy
npm run deploy
```

**Configuration for Vite** — set `base` to match repo name:
```javascript
// vite.config.js
export default {
  base: '/{repo-name}/',
  build: { outDir: 'dist' },
};
```

**GitHub Actions auto-deploy** on push to main:
```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci && npm run build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: dist
```

---

## Vercel

Best for preview deploys (every PR gets a unique URL) and zero-config static hosting.

```bash
# Install Vercel CLI
npm install -g vercel

# vercel.json — minimal config for static game
```

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": null
}
```

```bash
# Preview deploy (development)
vercel

# Production deploy
vercel --prod
```

**Environment variables** if your game uses a backend:
```bash
vercel env add GAME_API_URL production
```

---

## Generic Static Hosting

The game `dist/` output is self-contained. Deploy to any static host:

| Host | Command | Notes |
|---|---|---|
| Netlify | `netlify deploy --prod --dir dist` | Free tier generous |
| Cloudflare Pages | `wrangler pages deploy dist` | Global CDN |
| AWS S3 | `aws s3 sync dist/ s3://bucket-name --acl public-read` | Configure static website hosting |
| itch.io | Upload `dist/` as a zip | Game-specific, monetization built-in |
| Surge | `surge dist/ your-game.surge.sh` | Simplest possible deploy |

**itch.io specifics**:
1. Build: `npm run build`
2. Zip: `cd dist && zip -r ../game.zip .`
3. Upload `game.zip` as HTML game
4. Set viewport to match your game's canvas size

---

## Custom Domain

With GitHub Pages:
```bash
# Add CNAME record at DNS provider pointing to username.github.io
# Create CNAME file in dist/ before deploy:
echo "your-game.example.com" > dist/CNAME
npm run deploy
```

With Vercel:
```bash
vercel domains add your-game.example.com
# Follow DNS configuration instructions
```

---

## iOS Export via Capacitor

See `capacitor-ios.md` for the full workflow. Summary:

1. `npm install @capacitor/core @capacitor/ios`
2. `npx cap init "Game Name" com.yourname.gamename --web-dir dist`
3. `npm run build && npx cap sync`
4. `npx cap open ios` (opens Xcode)
5. Build from Xcode for simulator or device

---

## Error Handling

### Error: Game Loads But Assets Are 404
**Cause**: Asset paths are absolute (`/assets/player.png`) instead of relative (`assets/player.png`), or Vite `base` is wrong
**Fix**:
- Set Vite `base` to `./` for portable relative paths, or to `/{repo-name}/` for GitHub Pages subdirectory
- Run `grep -r '"/assets/' dist/` to find absolute paths
- Fix in source: use `import.meta.env.BASE_URL + 'assets/player.png'` in Vite projects

### Error: GitHub Pages Returns 404 on All Routes
**Cause**: SPA routing not configured — GitHub Pages serves only exact file paths
**Fix**: Add a `404.html` that redirects to `index.html`, or use hash-based routing (`/#/level1` instead of `/level1`).

### Error: Vercel Deploy Succeeds But Game Shows White Screen
**Cause**: Build output references source-map files or dev-only assets not present in production
**Fix**: Check browser console errors. Run `npm run build -- --mode production` locally and test the `dist/` output before deploying.

### Error: itch.io HTML Game Shows "This content cannot be displayed in a frame"
**Cause**: Missing headers or content security policy blocking iframe embedding
**Fix**: Add to your HTML: `<meta http-equiv="X-Frame-Options" content="ALLOWALL">`. Or use Vercel/Netlify and link from itch.io rather than embedding.
