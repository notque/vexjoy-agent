# Game review question bank

Ask many specific questions per screen, action, flow, and session to find how to improve a game. Each question is one judgment; code checks anything it can measure.

## How to run it
- One request per screen: screenshot(s) ≥1080 px in state + calibrated DOM facts + a one-line legend. Image tokens are billed once per request; each extra question costs only ~50–150 tokens. No limit on questions per request (the two token limits decide: state+longest question ≤32k on the image path). So ask ALL applicable questions per screen in one request.
- One judgment per question. Noul = yes/no; Score = ladder with observable signals; Choice = pick from options you write; Compare = A vs B in state.
- Every Choice: ask in reversed order too on a sample; report margins (2-option bar 1.5, else 2.0).
- Anything code can measure (links, counts, sizes, timings, overlaps) is a code check, not a Jev question.
- Put the requester's words verbatim in state, and the players' expectations.

## A. Per screen (screenshot)
Clarity and guidance
1. Noul: a new player can tell what this screen is for.
2. Noul: a new player can tell what to do next.
3. Noul: the most important action is the most visually prominent.
4. Noul: the player can tell what each button will do before pressing it.
5. Noul: numbers shown have enough context (units, good/bad, compared to what).
6. Noul: any term on screen would confuse a new player (list in state).
7. Noul: the player can tell what changed since last time they were here.
8. Score 0–3 information overload (0 = scannable in 3 s … 3 = wall of text/numbers).
Navigation
9. Noul: the player can tell where the other main sections are from here.
10. Noul: the player can tell how to go back.
11. Choice: which section would a new player try next (from nav options); compare with intended.
Fun and stakes
12. Score 0–3 fun (0 stakes not shown; 1 stakes shown; 2 consequences of choices shown; 3 anticipation and payoff).
13. Noul: the screen creates a reason to keep playing (a hook, goal, cliffhanger).
14. Noul: the player has a meaningful choice here (not a single obvious option).
15. Noul: the screen shows progress toward a goal.
16. Noul: there is a surprise or variety element.
17. Choice: which emotion does this screen most evoke (excitement / tension / pride / curiosity / boredom / confusion / frustration).
Juice and feel (static cues; motion uses pairs, section B)
18. Score 0–3 visual richness (flat → polished, themed art).
19. Noul: rewards look rewarding (size, colour, celebration).
20. Noul: the screen fits the game's theme/genre (for example a sports front office).
21. Noul: typography and art feel like one game.
Consistency (Compare against 2 house-style screens in state)
22. Noul: buttons look different from house style.
23. Noul: colours or type differ from house style.
24. Noul: spacing/layout grid differs.
25. Noul: the same thing is named differently from other screens (term list in state).
26. Noul: icons are used inconsistently.
Accessibility and mobile
27. Noul: some text is hard to read (contrast or size) — pair with measured contrast/px.
28. Noul: colour alone carries meaning.
29. Noul (mobile shot): the layout reads well at phone size.
30. Noul (mobile): a key action is hard to reach with a thumb — pair with measured tap size.
Defects (one per kind, intent in wording, DOM fact in wording)
31–36. cut off / overlap / blank panel / error text / broken image / placeholder or debug text.
Improvement
37. Choice: single best improvement for this screen (4–6 concrete options: clarity / fun / juice / consistency / mobile).
38. Choice: which category is this screen weakest in (clarity, fun, juice, consistency, navigation).
39. Noul: this screen could be merged or removed without loss.
40. Noul: anything here would make a player quit or complain.

## B. Per key action (before/after screenshot pair)
41. Noul: the result of the action is obvious.
42. Score 0–3 feedback strength (none → state change → highlighted → celebration).
43. Noul: the player can tell whether it was a good or bad outcome.
44. Noul: the action felt worth doing (reward vs effort).
45. Choice: best juice addition (screen shake / number pop / sound cue / animation / particle / reaction text / none needed).
46. Noul: the action needed more confirmation (risky and irreversible).
47. Noul: the action needed fewer steps.

## C. Per flow (sequence of screens as numbered images + click count, time, retries)
48. Noul: the flow has an unnecessary step.
49. Noul: the player could get lost mid-flow.
50. Score 0–3 pacing (drags → snappy).
51. Choice: the step to cut or merge.
52. Noul: the flow ends with a clear payoff.

## D. Per session / whole game (state = coverage table, timings, per-screen scores, run log)
53. Choice: the biggest reason a new player would quit in the first 10 minutes.
54. Choice: the section that most needs work.
55. Noul: the core loop is clear by the end of the first session.
56. Noul: there is enough variety across a run/season.
57. Score 0–3 difficulty curve (spiky → smooth).
58. Choice: the top missing feature players would expect from this genre.
59. Choice: the highest-value fun idea (from collected per-screen ideas).
60. Choice: the highest-value juice idea.
61. Noul: the game teaches its systems without a manual.
62. Noul: progression feels rewarding over a session.
63. Compare: our screen vs a genre reference screenshot (rated by the requester) — "how far from the reference" Score.

## E. Code checks (not Jev)
- Every link/button clicked: status, console errors, dead/no-op clicks, route rendered.
- Coverage: sections reached vs full route list, clicks from home.
- Term list: nav labels, headings, buttons across screens; near-duplicates.
- Measured: tap sizes, contrast ratios, overlaps (bounding boxes), load times, layout shift.
- Dead ends: screens with no way forward/back.

## Report
Per screen: all scores in one table row. Then: release blockers, top fun ideas, top juice ideas, consistency list, broken links, coverage gaps. Each finding: screenshot path + the decisive number + margin.
