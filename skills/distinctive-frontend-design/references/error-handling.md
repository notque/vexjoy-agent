## Error Handling

### Error: "Validation failed -- banned font detected"
Cause: Selected font is on the banned list (Inter, Roboto, Arial, Helvetica, system fonts, Space Grotesk) or appears in a CSS fallback stack
Solution:
1. Select alternative from `references/font-catalog.json` -- all catalog fonts are pre-approved
2. Verify fallback stacks do not include banned fonts (e.g., `sans-serif` alone is banned)
3. Re-run font validator to confirm resolution

### Error: "Cliche color scheme detected"
Cause: Palette analyzer flags purple gradient on white, generic blue primary, or evenly distributed colors
Solution:
1. Review `references/color-inspirations.json` for culturally-grounded alternatives
2. Ensure clear 60/30/10 dominance ratio -- if colors are evenly split, commit to a dominant
3. Choose inspiration from project context (audience, purpose, emotion), not convenience
4. Re-run palette analyzer to confirm resolution

### Error: "Low distinctiveness score (< 80)"
Cause: Design lacks personality, shows timid commitment to aesthetic direction, or has multiple marginal issues
Solution:
1. Review validation report for the specific weak areas
2. Strengthen contextual elements: add custom textures, commit fully to the aesthetic direction
3. Check if font + color + background form a cohesive story or feel disconnected
4. Iterate and re-validate -- max 3 attempts before reconsidering the aesthetic direction
