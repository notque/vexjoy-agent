---
title: Channel Evaluation — CAC/LTV Models, Content Funnel Stages, Channel Matrices
domain: growth-strategy
level: 3
skill: growth-strategy
---

# Channel Evaluation Reference

> **Scope**: Channel evaluation matrices, CAC/LTV models for content and product channels, and content funnel stage mapping. Covers the decision of which 2-3 channels a solo creator or small team should invest in, and how to measure whether those channels are working.
> **Version range**: Platform-agnostic — specific platform metrics (impressions, reach algorithms) change; the evaluation framework does not.
> **Generated**: 2026-04-09 — validate platform-specific CAC benchmarks against current data.

---

## Overview

Most growth strategy failures are channel diffusion failures: too many channels, each receiving insufficient investment to reach escape velocity. Organic channels (SEO, community, referral) need 6-12 months of consistent investment before producing measurable returns. Solo creators who spread across 5 channels simultaneously give each channel 4 months — exactly the minimum needed before any signal emerges. Channel evaluation helps you pick fewer channels and sustain them long enough to learn.

---

## Channel Evaluation Matrix

Score each channel before committing investment. Score 1-10 per dimension. Customize weights for your constraint.

| Channel | Reach Potential | Audience Fit | Creator Fit | Time to Signal | CAC | Compounding | Total Score |
|---------|----------------|--------------|-------------|----------------|-----|-------------|-------------|
| **Weight** | **2×** | **3×** | **2×** | **2×** | **3×** | **3×** | **/15 dims** |
| SEO / organic search | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |
| Email newsletter | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |
| Twitter/X | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |
| LinkedIn | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |
| YouTube | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |
| Podcast | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |
| Reddit / communities | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |
| Paid (Meta/Google) | ___ | ___ | ___ | ___ | ___ | ___ | **calc** |

**Scoring guides**:
- **Reach Potential** (1-10): Size of addressable audience on this channel relative to your niche
- **Audience Fit** (1-10): Is your specific audience active and engaged on this channel?
- **Creator Fit** (1-10): Do you enjoy producing this format? Can you sustain it for 12 months?
- **Time to Signal** (1-10): 10 = signal in weeks (paid ads), 1 = signal in 12+ months (SEO from zero)
- **CAC** (1-10): 10 = near-zero CAC (referral), 1 = very high CAC (paid acquisition in competitive niche)
- **Compounding** (1-10): Does it compound over time? 10 = SEO builds permanently; 1 = paid stops instantly when you stop paying

**Worked example** (technical blog for Go developers):

| Channel | Reach | Fit | Creator | Signal | CAC | Compound | Score |
|---------|-------|-----|---------|--------|-----|----------|-------|
| SEO | 7 | 9 | 7 | 2 | 9 | 10 | **144** |
| Email | 5 | 8 | 9 | 5 | 8 | 7 | **126** |
| Twitter/X | 8 | 6 | 5 | 7 | 7 | 4 | **102** |
| YouTube | 8 | 5 | 3 | 4 | 7 | 8 | **97** |

Decision: Invest in SEO + email (top 2). Twitter as lightweight amplifier (< 2 hrs/week). YouTube deferred until email list hits 1,000.

---

## CAC / LTV Model for Content Channels

For content-based businesses, "customer" = subscriber/reader. Adapt definitions for your business model.

### CAC Calculation

```
## CAC by Channel

### SEO
- Content creation cost per post: ___ hours × $___/hour = $___
- Monthly organic signups attributed to SEO: ___
- Monthly CAC (SEO): $___/month ÷ ___ signups = $___/subscriber

### Email (direct)
- Monthly email campaign cost: $___
- New subscribers from email campaigns: ___
- Monthly CAC (email): $___/month ÷ ___ signups = $___/subscriber

### Social (Twitter/LinkedIn/etc.)
- Hours/month × $___/hour = $___
- New subscribers attributed to social: ___
- Monthly CAC (social): $___/month ÷ ___ signups = $___/subscriber

### Paid Acquisition
- Ad spend per month: $___
- Paid subscribers acquired: ___
- Monthly CAC (paid): $___/month ÷ ___ signups = $___/subscriber
```

### LTV Calculation

```
## LTV by Subscriber Type

### Free subscriber
- Revenue per free subscriber: $0 direct
- Indirect value: [referrals × conversion rate × paid LTV] + [sponsored post CPM equivalent]
- Estimated LTV: $___

### Paid subscriber (if applicable)
- Monthly or annual revenue: $___/subscriber
- Average retention: ___ months
- LTV: $___/month × ___ months = $___

### LTV:CAC Ratio by Channel
Channel | LTV | CAC | Ratio | Verdict
SEO | $___ | $___ | ___:1 | ___
Email | $___ | $___ | ___:1 | ___
Social | $___ | $___ | ___:1 | ___
```

**Benchmark ratios**:
- LTV:CAC < 1:1 = destroying value, stop this channel
- LTV:CAC 1-3:1 = borderline; only continue if compounding effect is strong
- LTV:CAC 3-10:1 = healthy; sustain and optimize
- LTV:CAC > 10:1 = exceptional; increase investment

---

## Content Funnel Stage Mapping

Map your content to funnel stages. A common failure is creating only awareness content with no conversion path.

| Stage | Goal | Content Types | Success Metric | Conversion Action |
|-------|------|--------------|----------------|-------------------|
| **Awareness** | Reach new people | SEO posts, viral social, podcast appearances | Unique visitors, impressions | — |
| **Interest** | Deepen engagement | Long-form content, tutorials, case studies | Time on page, scroll depth, return visits | Subscribe to email |
| **Consideration** | Build trust | Email series, deep dives, comparison guides | Email open rate, click-through | Follow CTA, book call |
| **Conversion** | Monetize | Product pages, sales emails, webinars | Revenue, conversion rate | Purchase |
| **Retention** | Keep and grow | Community, updates, exclusive content | Churn rate, referral rate | Upgrade, referral |

**Funnel audit** — classify your last 10 pieces of content:

```
Content Item | Funnel Stage | Has Conversion CTA? | Next Step for Reader?
1. | | |
2. | | |
...
```

Common finding: 80% of content is Awareness. No Interest or Consideration content means the funnel leaks. Readers who want to go deeper have nowhere to go.

---

## Channel Sustainability Check

Before committing to a channel, verify you can sustain it for 6 months minimum.

| Channel | Weekly Hours Required | Monthly Cost | Can Sustain 6 months? |
|---------|-----------------------|-------------|----------------------|
| SEO blog (1 post/week) | 6-10 hours | $0-50 (tools) | ___ |
| Email newsletter (1x/week) | 2-4 hours | $20-100 (provider) | ___ |
| Twitter (daily) | 1-2 hours | $0 | ___ |
| YouTube (1 video/week) | 8-15 hours | $0-200 (equipment) | ___ |
| Podcast (1 episode/week) | 4-8 hours | $20-50 (hosting) | ___ |

**Capacity reality check**:
```
Available hours/week for growth work: ___
Total hours required for selected channels: ___
Buffer (should be 20%+): ___

If selected channel hours > 80% of available hours: remove a channel.
```

---

## Anti-Patterns

### Platform-native metrics as success metrics
**What it looks like**: "We got 50 retweets!" — but zero new email subscribers, zero traffic, zero revenue.
**Why wrong**: Platform metrics (likes, impressions, follower count) measure engagement with the platform, not growth of YOUR asset. A viral tweet that doesn't move subscribers is entertainment, not growth.
**Fix**: Track only metrics that connect to your owned channel (email subscribers, direct traffic) or revenue. Report platform metrics only as leading indicators of owned metrics.

### Optimizing for CAC without measuring LTV
**What it looks like**: "Reddit drives the cheapest subscriber acquisition at $0.50 each."
**Why wrong**: If Reddit subscribers have 50% lower LTV (because they signed up for one specific post and have low topic affinity), the channel is less efficient than it appears.
**Fix**: Track subscriber cohort behavior by acquisition channel. Measure 90-day engagement rate per channel. CAC × engagement rate gives channel-adjusted CAC.

### Treating all funnel stages as the same
**What it looks like**: Every piece of content ends with "check out my other posts." No direct subscribe CTAs, no product mentions, no differentiated asks by content type.
**Why wrong**: Awareness content with hard conversion CTAs drives away top-of-funnel readers. Consideration content without conversion paths wastes intent. Each stage needs its own CTA.
**Fix**: Assign one primary CTA per funnel stage. Awareness = subscribe. Interest = download resource. Consideration = book a call or trial. Conversion = purchase.

---

## See Also

- `audience-segmentation.md` — ICP scoring, persona matrices, audience segmentation for channel targeting
- `skills/growth-strategy/SKILL.md` — full growth strategy workflow with 90-day planning
