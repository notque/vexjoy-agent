# Outline Examples

Real outline examples from YourBlog posts demonstrating proper structure and format.

---

## Example 1: Problem-Solution Outline

**Topic brief:** "Spent 3 hours debugging why Hugo builds locally but fails on Cloudflare Pages. Error was cryptic. Finally figured out it was Hugo version mismatch."

```
===============================================================
 OUTLINE: Hugo Version Hell on Cloudflare Pages
===============================================================

 Structure: Problem-Solution
 Estimated Length: 1,200-1,500 words (~5 min read)

 FRONTMATTER:
   title: "Hugo Version Hell on Cloudflare Pages"
   date: 2024-12-24
   tags: ["hugo", "cloudflare-pages", "debugging", "ci-cd"]
   summary: "Why Hugo builds locally but fails on Cloudflare,
   and how to fix version mismatches in CI/CD environments."

 SECTIONS:

 1. The Vex: Builds Work Locally, Fail in CI [200-300 words]
    hugo --minify works perfectly on my machine. Push to
    Cloudflare Pages: "Error: failed to extract shortcode."
    Three hours of staring at identical code, different results.
    The error message points to a shortcode that renders fine locally.

 2. The Wrong Turns [300-400 words]
    First thought: theme submodule not pulling correctly.
    Checked .gitmodules, verified submodule init. Still fails.
    Second thought: maybe a caching issue. Clear cache, rebuild.
    Same error. Third thought: shortcode syntax changed? Compared
    against Hugo docs. Syntax is correct. Starting to question reality.

 3. The Actual Problem: Version Mismatch [400-500 words]
    Cloudflare Pages defaults to Hugo 0.54 (ancient). My local
    machine runs 0.123. The shortcode syntax I'm using was added
    in 0.109. Show how to check Cloudflare's Hugo version in build
    logs. Explain the HUGO_VERSION environment variable solution.
    Include the exact Cloudflare Pages configuration needed.

 4. Lessons: Version-Lock Your Build Tools [200-300 words]
    Always specify exact versions in CI/CD. Create a checklist:
    check local version, check CI version, document in README.
    Other tools with similar gotchas: Node version, Go version.
    The broader principle: local and CI must match exactly.

===============================================================
 ALTERNATIVE STRUCTURES:

 -> Walkthrough: Step-by-step guide to setting up Hugo on
    Cloudflare Pages correctly from the start (more prescriptive,
    less debugging narrative)

 -> Technical Explainer: Focus on how Cloudflare Pages build
    environment works, why defaults are what they are
    (deeper on the "how" vs the "what happened")
===============================================================
```

---

## Example 2: Technical Explainer Outline

**Topic brief:** "Go 1.22 changed how loop variables work. This affects a lot of existing code. Want to explain what changed and why."

```
===============================================================
 OUTLINE: Go 1.22's Loop Variable Revolution
===============================================================

 Structure: Technical Explainer
 Estimated Length: 1,400-1,700 words (~6 min read)

 FRONTMATTER:
   title: "Go 1.22's Loop Variable Revolution"
   date: 2024-12-24
   tags: ["go", "golang", "go-1.22", "loop-variables"]
   summary: "Go 1.22 changes loop variable scoping. Here's what
   changed, why it matters, and what to check in your code."

 SECTIONS:

 1. What Changed [200-250 words]
    In Go 1.21 and earlier, for-loop variables were scoped to
    the entire loop. In Go 1.22+, each iteration gets its own
    variable. Show the classic goroutine-in-loop bug and how
    it's now fixed by default. One code example, before and after.

 2. Why This Matters More Than You Think [350-450 words]
    The goroutine bug affected almost every Go developer at some
    point. The workaround (shadowing with x := x) was ugly and
    easy to forget. But this change also affects closures in
    general, not just goroutines. Show the closure capture case.
    Discuss backward compatibility: code that relied on the old
    behavior will silently change meaning.

 3. How It Works Under the Hood [400-500 words]
    The compiler now generates a new variable for each iteration.
    Explain the memory model implications. Show the generated
    assembly difference (brief, illustrative). Discuss the
    GOEXPERIMENT=loopvar that allowed early testing. Explain
    how go vet catches code that might change behavior.

 4. What To Do About Your Code [250-350 words]
    Run go vet with the loopvar check. Look for closures in
    loops, especially with goroutines. Most code gets safer,
    but some might rely on shared variable. Testing strategy:
    run tests with Go 1.21 and 1.22, diff results. Mention
    the go.mod go version directive behavior.

===============================================================
 ALTERNATIVE STRUCTURES:

 -> Problem-Solution: Frame around a specific bug caused by
    old behavior, then reveal the language change as the fix
    (more narrative, less comprehensive)

 -> Comparison: Go's approach vs other languages' loop
    semantics (broader context, less practical)
===============================================================
```

---

## Example 3: Walkthrough Outline

**Topic brief:** "Want to explain how to set up a Hugo blog on Cloudflare Pages from scratch."

```
===============================================================
 OUTLINE: Hugo + Cloudflare Pages: Zero to Deployed
===============================================================

 Structure: Walkthrough
 Estimated Length: 1,300-1,600 words (~6 min read)

 FRONTMATTER:
   title: "Hugo + Cloudflare Pages: Zero to Deployed"
   date: 2024-12-24
   tags: ["hugo", "cloudflare-pages", "tutorial", "static-site"]
   summary: "Complete setup guide for deploying a Hugo blog to
   Cloudflare Pages with automatic builds on git push."

 SECTIONS:

 1. What You'll Have [100-150 words]
    A Hugo blog with a theme, deployed to Cloudflare Pages,
    automatically rebuilding when you push to GitHub. Free
    hosting, fast CDN, custom domain ready. The stack: Hugo
    for generation, GitHub for source, Cloudflare for hosting.

 2. Prerequisites [150-200 words]
    Hugo installed locally (show version check command).
    GitHub account with a repository ready. Cloudflare account
    (free tier works). Basic command line comfort. If you're
    missing any: links to setup guides, not reproduced here.

 3. Step-by-Step Setup [550-700 words]
    Step 1: Initialize Hugo site (hugo new site, expected output)
    Step 2: Add theme as git submodule (exact commands, verify)
    Step 3: Configure hugo.toml (minimal config that works)
    Step 4: Create first post (hugo new content, frontmatter)
    Step 5: Test locally (hugo server -D, what to check)
    Step 6: Push to GitHub (commands, verify in browser)
    Step 7: Connect Cloudflare Pages (UI walkthrough, key settings)
    Step 8: Set HUGO_VERSION (critical, with exact value)
    Step 9: Trigger first build (what success looks like in logs)

 4. Common Gotchas [200-300 words]
    Theme not found: submodule not initialized, fix commands.
    Build succeeds but blank page: baseURL wrong, fix.
    CSS missing: theme asset pipeline needs extended Hugo.
    Slow builds: clear cache in Cloudflare dashboard.
    Each with specific symptom and fix.

 5. You're Live [100-150 words]
    Verify: visit your-project.pages.dev. Check build status
    in Cloudflare dashboard. Next steps: custom domain setup,
    more posts, theme customization. Link to PaperMod docs.

===============================================================
 ALTERNATIVE STRUCTURES:

 -> Problem-Solution: Focus on a specific deployment failure
    and how to fix it (narrower, for troubleshooting)

 -> Technical Explainer: How Cloudflare Pages build process
    works under the hood (deeper, less practical)
===============================================================
```

---

## Example 4: Comparison Outline

**Topic brief:** "Trying to choose between Cloudflare Pages and Vercel for hosting my Hugo site. Both are free, both work with Hugo."

```
===============================================================
 OUTLINE: Cloudflare Pages vs Vercel for Hugo Sites
===============================================================

 Structure: Comparison
 Estimated Length: 1,200-1,500 words (~5 min read)

 FRONTMATTER:
   title: "Cloudflare Pages vs Vercel for Hugo Sites"
   date: 2024-12-24
   tags: ["cloudflare-pages", "vercel", "hugo", "hosting"]
   summary: "Comparing Cloudflare Pages and Vercel for static
   Hugo sites: build times, features, limits, and my pick."

 SECTIONS:

 1. The Decision Point [150-200 words]
    Both are free, both work with GitHub, both deploy Hugo
    sites easily. So why does the choice matter? Build times
    affect iteration speed. Free tier limits affect growth.
    CDN coverage affects global performance. Edge functions
    might matter for future features.

 2. The Contenders [400-500 words]
    Cloudflare Pages: Part of Cloudflare ecosystem. Unlimited
    bandwidth on free tier. Uses their global CDN. Build
    environment quirks (older defaults). Cloudflare Access
    for staging environments.

    Vercel: Built for Next.js but works with any static site.
    Fast builds. Preview deployments with unique URLs. More
    generous compute limits. Better build logs and error
    messages.

 3. Head-to-Head Comparison [350-450 words]
    Build speed: Vercel faster for cold starts, similar once
    cached. Both under 60s for typical Hugo site.
    Free tier limits: Cloudflare unlimited bandwidth vs Vercel
    100GB. Cloudflare 500 builds/month vs Vercel 6000.
    Hugo support: Both require setting HUGO_VERSION. Vercel
    defaults to newer Hugo. Cloudflare needs explicit config.
    CDN performance: Cloudflare slightly better in Asia/Europe.
    Vercel slightly better in US.
    Developer experience: Vercel better logs and error messages.
    Cloudflare better Cloudflare ecosystem integration.

 4. My Pick: Cloudflare Pages [200-300 words]
    For a Hugo blog: Cloudflare Pages. Unlimited bandwidth
    means never worrying about traffic spikes. Cloudflare
    ecosystem (DNS, email routing, Access) in one dashboard.
    Vercel better if: you want preview URLs for every PR,
    you might add Next.js later, you prefer their DX.
    The real answer: both work great, pick one and build.

===============================================================
 ALTERNATIVE STRUCTURES:

 -> Technical Explainer: Deep dive into how each platform's
    build pipeline works (more technical, less practical)

 -> Walkthrough: Setting up Hugo on one platform specifically
    (narrower, more actionable for one choice)
===============================================================
```

---

## Outline Quality Checklist

Use this to verify any outline before presenting:

- [ ] Working title is specific and interesting
- [ ] Structure type matches the content
- [ ] Word counts per section add up to total
- [ ] Each section summary is 2-3 sentences
- [ ] Section names are specific, not generic
- [ ] Frontmatter includes realistic tags
- [ ] Summary is actually a summary (fits in list view)
- [ ] At least 2 alternative structures offered
- [ ] Reading time calculated (~250 wpm)
- [ ] YourBlog identity present (technical, direct, no fluff)
