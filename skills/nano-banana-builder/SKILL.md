---
name: nano-banana-builder
description: |
  Build Next.js web applications with Google Gemini Nano Banana image generation
  APIs (gemini-2.5-flash-image, gemini-3-pro-image-preview). Use when creating
  image generators, editors, galleries, or any app integrating conversational
  image generation with server actions, API routes, and storage. Use for "image
  generation app", "nano banana", "text to image", "AI image generator", or
  "gemini image". Do NOT use for non-Gemini models, Python/Go backends, model
  fine-tuning, or image classification/input tasks.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
command: /nano-banana
routing:
  triggers:
    - nano banana
    - gemini image generation
    - AI image generator
    - image generation app
    - gemini-2.5-flash-image
    - gemini-3-pro-image-preview
    - web image generator
  pairs_with:
    - typescript-frontend-engineer
    - nodejs-api-engineer
    - universal-quality-gate
---

# Nano Banana Builder

## Operator Context

This skill operates as an operator for building production web applications powered by Google's Nano Banana image generation APIs. It implements the **Phased Build** architectural pattern -- Scaffold, Integrate, Polish, Verify -- with **Domain Intelligence** embedded in model selection, conversational editing, and production hardening.

### Hardcoded Behaviors (Always Apply)

- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before building
- **Exact Model Names Only**: Use `gemini-2.5-flash-image` or `gemini-3-pro-image-preview` exclusively. Never invent model strings, add date suffixes, or guess names.
- **Server-Side API Calls**: All Gemini API calls go through server actions or API routes. Never expose API keys client-side.
- **Storage Over Base64**: Store generated images in object storage (Vercel Blob, S3/R2) and persist URLs, not raw base64 in databases.
- **Rate Limit Handling**: Every production integration must include rate limiting with user-friendly feedback.
- **Conversational Editing**: Leverage multi-turn history for iterative refinement rather than one-shot generation.

### Default Behaviors (ON unless disabled)

- **Model Selection by Use Case**: Flash for speed/volume, Pro for quality/text rendering
- **Loading State UX**: Show progress indicators during 5-30s generation time
- **Error Boundaries**: Wrap generation components in error boundaries with retry
- **Debounced Input**: Require explicit user action to generate, never on keystroke
- **Unique Design Per App**: Vary UI style, color, layout, and interaction to fit purpose
- **Environment Variable Validation**: Check for required keys at startup

### Optional Behaviors (OFF unless enabled)

- **Batch Generation**: Generate multiple images in parallel with queue management
- **Image Composition**: Combine multiple generated images into composites
- **Style Transfer**: Apply reference styles across generations
- **Gallery Persistence**: Save generation history with browsing and search

## What This Skill CAN Do

- Build complete image generation web applications with Next.js
- Implement server actions and API routes for both Gemini image models
- Handle iterative, multi-turn image editing conversations via useChat
- Configure object storage (Vercel Blob, S3/R2) for generated images
- Implement rate limiting and quota management with Upstash Redis
- Select the correct model based on speed, quality, and cost tradeoffs

## What This Skill CANNOT Do

- Use non-Gemini image models (DALL-E, Midjourney, Stable Diffusion)
- Deploy to non-Node.js environments (Python, Go, etc.)
- Implement custom model fine-tuning or training
- Handle image input/classification (that is Gemini Vision, not Nano Banana)
- Skip any of the 4 build phases

---

## Instructions

### CRITICAL: Valid Model Names

Only two model strings exist for image generation. Use them exactly as written.

| Model String (exact) | Alias | Best For |
|----------------------|-------|----------|
| `gemini-2.5-flash-image` | Nano Banana | Fast iterations, drafts, high volume (2-5s) |
| `gemini-3-pro-image-preview` | Nano Banana Pro | Quality output, text rendering, 2K resolution |

**Common wrong names**: `gemini-2.5-flash-preview-05-20` (text model suffix), `gemini-2.5-pro-image` (Pro does not generate images), `gemini-3-flash-image` (does not exist), `gemini-pro-vision` (image input, not generation).

### Phase 1: SCAFFOLD

**Goal**: Set up the Next.js project structure with dependencies and environment.

**Step 1: Initialize project and install dependencies**

```bash
npm install @ai-sdk/google ai @ai-sdk/react
# Storage (pick one):
npm install @vercel/blob    # Vercel Blob
# or configure S3/R2 via aws-sdk
# Rate limiting (optional):
npm install @upstash/ratelimit @upstash/redis
```

**Step 2: Configure environment variables**

```bash
# .env.local
GEMINI_API_KEY=your_api_key_here
BLOB_READ_WRITE_TOKEN=your_vercel_token  # if using Vercel Blob
```

**Step 3: Define the application structure**

```markdown
## App Structure
- app/actions/generate.ts    -- Server action for image generation
- app/api/generate/route.ts  -- API route (if using useChat)
- app/components/            -- React client components
- lib/storage.ts             -- Storage abstraction
- lib/rate-limit.ts          -- Rate limiting (if production)
```

**Gate**: Project initializes, dependencies install, env vars configured. Proceed only when gate passes.

### Phase 2: INTEGRATE

**Goal**: Wire up Gemini image generation with server-side API calls and client components.

**Step 1: Create server action or API route**

```typescript
// app/actions/generate.ts
'use server'
import { google } from '@ai-sdk/google'
import { generateText } from 'ai'

export async function generateImage(prompt: string) {
  const result = await generateText({
    model: google('gemini-2.5-flash-image'),
    prompt,
    providerOptions: {
      google: {
        responseModalities: ['IMAGE'],
        imageConfig: { aspectRatio: '16:9' }
      }
    }
  })
  return result.files[0] // { base64, uint8Array, mediaType }
}
```

**Step 2: Build client component with loading states**

Use `useChat` for multi-turn editing or direct server action calls for single-shot generation. Always include loading indicators and error display.

**Step 3: Connect storage**

Upload generated images to object storage immediately. Return persistent URLs, not base64.

**Gate**: User can enter a prompt and receive a generated image displayed in the UI. Proceed only when gate passes.

### Phase 3: POLISH

**Goal**: Harden for production with rate limiting, error handling, and design variation.

**Step 1: Add rate limiting**

Implement per-user rate limits using Upstash Redis or in-memory fallback. Show friendly wait messages on 429 responses.

**Step 2: Implement error boundaries and retry**

Wrap generation in try/catch with specific handling for 429 (rate limit), 401 (bad key), 400 (content policy), and network timeout. Provide user-visible feedback for each case.

**Step 3: Apply unique design**

Match UI style to the application purpose. Avoid generic AI startup aesthetics. Vary color scheme, layout, typography, and interaction pattern intentionally.

**Gate**: App handles all error cases gracefully and has intentional visual design. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm the application works end-to-end and meets production standards.

**Step 1**: Generate an image successfully with a test prompt

**Step 2**: Verify model name strings are exactly `gemini-2.5-flash-image` or `gemini-3-pro-image-preview`

**Step 3**: Confirm no API keys are exposed in client-side code or bundles

**Step 4**: Test error states (invalid prompt, rate limit simulation, missing env var)

**Step 5**: Verify images persist in storage with retrievable URLs

**Step 6**: Run full test suite if tests exist, no regressions

**Gate**: All verification steps pass. Build is complete.

---

## Error Handling

### Error: "Rate Limit Exceeded (429)"
Cause: Too many requests to Gemini API within quota window
Solution:
1. Implement rate limiting middleware (Upstash Redis or in-memory)
2. Show user-friendly wait message with estimated retry time
3. Queue requests if burst traffic is expected

### Error: "Invalid API Key (401)"
Cause: Missing or incorrect GEMINI_API_KEY in environment
Solution:
1. Verify key exists in `.env.local` and is loaded server-side
2. Check key has image generation permissions enabled
3. Never expose key in client components or API responses

### Error: "Content Policy Violation (400)"
Cause: Prompt triggers Gemini safety filters
Solution:
1. Display clear user guidance on acceptable content
2. Do not retry the same prompt automatically
3. Log violations for monitoring without storing prompt content

### Error: "Network Timeout or Generation Failure"
Cause: Generation exceeding timeout or transient network issue
Solution:
1. Implement retry with exponential backoff (max 3 attempts)
2. Show progress indicator during the 5-30s generation window
3. Fall back to cached/placeholder image if all retries fail

---

## Anti-Patterns

### Anti-Pattern 1: Inventing Model Names
**What it looks like**: Using `gemini-2.5-flash-preview-05-20` or `gemini-2.5-pro-image` for generation
**Why wrong**: These model strings do not support image generation. Date suffixes belong to text models, and 2.5 Pro has no image output capability.
**Do instead**: Use exactly `gemini-2.5-flash-image` or `gemini-3-pro-image-preview`. No variations.

### Anti-Pattern 2: Exposing API Keys Client-Side
**What it looks like**: Calling Gemini directly from React components or embedding keys in client bundles
**Why wrong**: Credentials are visible in browser DevTools, enabling abuse and billing attacks.
**Do instead**: Route all API calls through server actions or API routes. Store keys in environment variables accessed only server-side.

### Anti-Pattern 3: Storing Base64 in Database
**What it looks like**: Saving raw base64 image data directly to PostgreSQL or MongoDB
**Why wrong**: Bloats database size, increases query latency, and makes backups expensive.
**Do instead**: Upload to object storage (Vercel Blob, S3, R2) immediately after generation. Persist only the URL.

### Anti-Pattern 4: Ignoring Multi-Turn Context
**What it looks like**: Treating every generation as a fresh request with no conversation history
**Why wrong**: Discards Nano Banana's strongest feature -- conversational editing and iterative refinement.
**Do instead**: Track generation history as chat messages. Use `useChat` to enable natural language editing of previous results.

### Anti-Pattern 5: No Loading States
**What it looks like**: Submit button goes disabled with no visual feedback for 5-30 seconds
**Why wrong**: Users assume the app is broken and spam-click, wasting quota and degrading UX.
**Do instead**: Show skeleton loaders, progress bars, or estimated wait time during generation.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I know the model name" | Wrong model strings silently fail or error | Verify against exact list |
| "Base64 is fine for now" | Technical debt compounds fast with image data | Use object storage from day one |
| "Rate limiting can wait" | First production spike causes 429 cascade | Implement before deploying |
| "Loading state is cosmetic" | 5-30s silence destroys user trust | Always show generation progress |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/advanced-patterns.md`: Server actions, API routes, client components, multi-image composition
- `${CLAUDE_SKILL_DIR}/references/configuration.md`: Provider options, storage setup, rate limiting, cost optimization
