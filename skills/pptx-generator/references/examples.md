# PPTX Generator Examples

## Example 1: Tech Talk from Outline

User says: "Create a 10-slide presentation about our new microservices architecture"
Actions:
1. GATHER: Topic = microservices migration, audience = engineering team, type = tech talk, 10 slides
2. DESIGN: Select Tech palette, build slide map with title, 6 content slides, 1 two-column (monolith vs micro), 1 section divider, closing. Present for approval.
3. GENERATE: Run `generate_pptx.py` with slide map and Tech palette
4. CONVERT: PPTX to PNGs via LibreOffice
5. QA: Subagent inspects 10 slide images, finds title text clipped on slide 4, fixes in iteration 2
6. OUTPUT: `microservices-architecture.pptx`, 10 slides, Tech palette, QA passed

## Example 2: Pitch Deck from Document

User says: "Turn this business plan into a pitch deck" (attaches document)
Actions:
1. GATHER: Extract key sections from business plan (problem, solution, market, traction, team, ask), type = pitch deck, 12 slides
2. DESIGN: Select Sunset palette for startup energy, build slide map with standard pitch structure. Present for approval.
3. GENERATE: Run script with slide map
4. CONVERT: PPTX to PNGs
5. QA: Subagent catches identical layout on 4 consecutive slides, fixes by inserting quote and two-column layouts
6. OUTPUT: `pitch-deck.pptx`, 12 slides, Sunset palette, QA passed after 2 iterations

## Example 3: Status Update (No LibreOffice)

User says: "Quick status update slides for the weekly standup, 5 slides"
Actions:
1. GATHER: Topic = weekly status, audience = team, type = status update, 5 slides
2. DESIGN: Select Minimal palette, build compact slide map. Present for approval.
3. GENERATE: Run script, structural validation passes
4. CONVERT: LibreOffice not available, skip visual QA
5. QA: Skipped
6. OUTPUT: `weekly-status.pptx`, 5 slides, Minimal palette, visual QA skipped
