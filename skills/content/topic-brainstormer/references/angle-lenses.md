# Angle Lenses

Six lenses for generating distinct angles on a single topic. Use during DECIDE when the task asks for angles on a story or topic rather than fresh topic candidates. For angle work, the "so what?" gate below replaces the three-question content quality filter — news-peg and perspective angles need a reader payoff, not a personal frustration history.

## The six lenses

Apply each lens to the topic; each produces at most one kept angle.

| Lens | Question it asks | Example (topic: a city bans e-scooters) |
|------|------------------|------------------------------------------|
| 1. Perspective shift | Whose view changes the story? Worker, customer, regulator, competitor, newcomer. | "What the ban looks like to the gig riders who charged the fleet overnight" |
| 2. Ladder of abstraction | One rung up (the trend this instance proves) or one rung down (the single concrete case). | Up: "Cities are regulating first, measuring later". Down: "One commuter's 40-minute detour" |
| 3. News values | Which classic value carries it: conflict, proximity, novelty, prominence, impact, human interest? | Conflict: "Council vs. the operators' lobbying blitz" |
| 4. Data angle | What does the dataset say that the narrative misses? Counts, trends, outliers, comparisons. | "Injury reports fell 12% the year before the ban — the data behind the vote" |
| 5. Contrarian | What if the consensus framing is wrong or backwards? | "The ban may put more cars, not fewer, on downtown streets" |
| 6. Timeliness peg | Why now? What current event, anniversary, season, or deadline makes this urgent today? | "Three more cities vote next month — this ban is the template" |

## Distinctness rule: one lens per kept angle

Each kept angle maps to exactly one lens. Two angles from the same lens are wordings of the same angle — keep the stronger one. This makes distinctness structural: a six-angle output is six genuinely different stories, checked by lens tag rather than by judgment call. Tag every kept angle with its lens.

## The "so what?" gate

Every kept angle must answer in one sentence: **why does the reader care?** The answer names a concrete reader payoff — a decision they can make, a risk they now see, a belief that just changed. "It's interesting" fails the gate. An angle with no answer is refused and logged.

## Refused-angles log

Log every refused angle with its reason. The log keeps refusals auditable and stops the same weak angle from resurfacing in the next round.

| Refused angle | Lens | Reason refused |
|---------------|------|----------------|
| [angle, one line] | [lens name] | [failed "so what?" / duplicate lens / inaccurate to source] |

Three accepted refusal reasons: failed the "so what?" gate, duplicate lens (a stronger angle holds the slot), inaccurate to the source material.

## Output format

```markdown
## Angles: [topic]

1. **[Lens name]** — "[angle as a one-line story statement]"
   So what: [one-sentence reader payoff]
2. ...

### Refused
| Refused angle | Lens | Reason refused |
|---|---|---|
| ... | ... | ... |
```
