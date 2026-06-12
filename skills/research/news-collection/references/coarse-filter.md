# Coarse Filter

Verdicts and reason codes for Phase 2. The filter is a high-recall pass: its
job is to cheaply remove obvious junk while guaranteeing nothing important is
silently dropped.

## Verdicts

| Verdict | Meaning | Goes to freshness check |
|---------|---------|-------------------------|
| `keep` | On-topic, substantive, plausibly fresh | Yes |
| `monitor_only` | Worth watching: off-topic but high-magnitude, thin but developing, or relevance uncertain | Yes |
| `reject` | Junk: spam, ads, listicles, dead pages, clearly irrelevant | No |

Asymmetry rule: high-magnitude stories are downgraded to monitor_only at
most, never rejected — a false keep is cheap, a silent drop is expensive.
"High-magnitude" means a story a downstream editor would expect to have seen:
major-company moves, regulatory action, safety events, market-moving results.
When magnitude and relevance pull in opposite directions, magnitude wins the
floor: verdict `monitor_only`, reason `RC-OFFTOPIC-BIG`.

## Reason codes

| Code | Verdict it pairs with | Meaning |
|------|----------------------|---------|
| `RC-ONTOPIC` | keep | Directly on the collection topic |
| `RC-DEV` | keep | New development of a known story |
| `RC-OFFTOPIC-BIG` | monitor_only | Off-topic but high-magnitude; floor applied |
| `RC-THIN` | monitor_only | On-topic but little substance yet |
| `RC-UNCERTAIN` | monitor_only | Relevance unclear; resolved downstream |
| `RC-SPAM` | reject | Promotional, advertorial, SEO bait |
| `RC-IRRELEVANT` | reject | Clearly outside the topic, low magnitude |
| `RC-NOCONTENT` | reject | Dead link, paywall stub, empty page |

Every verdict carries exactly one code. Codes make rejections auditable: a
DELIVER-phase reviewer can scan reject reasons without rereading sources.

## Cheap-model dispatch

This phase runs on a cheap model when dispatched as a subagent. It needs
recall and pattern-matching, not deep judgment — the expensive reasoning
happens in the freshness check, which only sees survivors. Give the dispatched
model: the topic, the verdict and code tables above, the asymmetry rule, and
the items' five facts plus a text excerpt. Require one verdict + one code per
item, output as JSON.
