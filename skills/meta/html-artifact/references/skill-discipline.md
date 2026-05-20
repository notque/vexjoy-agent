# Skill Discipline: Why You Run The Assembler

Domain rules for `html-artifact`. Hand-authoring HTML past `assemble-template.py` is forbidden. This file explains why, what breaks, and how the validator enforces it.

---

## What Discipline Means Here

| Rule | Meaning |
|---|---|
| Run the assembler | Every artifact starts with `python3 scripts/assemble-template.py --shape <s> --theme <t> ...`. No exceptions. |
| Don't write `<!DOCTYPE html>` directly | If you find yourself typing the doctype, stop. The assembler emits it. |
| Don't pattern-match off a previous artifact | Copying yesterday's HTML skips the marker, the print CSS injection, and the auto-injected `theme-toggle`. |
| Don't patch generated output by adding `<style>` blocks at the top | Theme tokens come from `templates/themes/{theme}.css`. Add to that, not to the artifact. |
| Treat the validator as the authority | If `validate-artifact.py` rejects, the artifact is broken — even if it renders in your browser. |

---

## What Goes Wrong Without It

| Skipped step | Concrete failure |
|---|---|
| No `theme-toggle` injection | Artifact ships without light/dark switch. Verified absent in 2 prior session artifacts (SIEM deck, Hermes deck). User has to read whatever theme the LLM picked. |
| No print CSS | PDF clips: decks lose 4 of 9 slides; reports drop trailing pages; spec grids overflow page width. |
| No `data-shape` attribute | `to-pdf.py` falls back to letter portrait. Decks render at 8.5x11 instead of 13.333x7.5 landscape — content shrinks or clips. |
| No theme tokens | Hardcoded `#fff` and `#000` everywhere. Dark mode toggle has nothing to flip. Contrast ratios untested. |
| No shape CSS | Slides don't position absolutely, don't honor `.active`, no arrow-key nav wiring. The "deck" is just stacked divs. |
| No assembler marker | Validator rejects on sight. Pipeline halts at Phase 5 VALIDATE. |

---

## The Marker Contract

The assembler writes this comment near the top of every artifact:

```html
<!-- assembled by html-artifact v1.1 -->
```

| Property | Value |
|---|---|
| Position | Within first 20 lines, after `<!DOCTYPE html>` |
| Author | `assemble-template.py` only — never written by hand |
| Validator behavior | `validate-artifact.py` greps for `<!-- assembled by`. Missing = REJECT. |
| Version bump | When assembler output format changes, `v` bumps. Old markers still pass; the version is informational. |

The marker is the assembler's signature. If it's absent, the artifact didn't go through the assembler. The validator does not trust your claim that "it's basically the same output" — it checks the marker.

---

## Detection Commands

| Goal | Command |
|---|---|
| Fast check (just the marker) | `grep '<!-- assembled by' file.html` |
| Full check (marker + theme-toggle + shape + tokens) | `python3 scripts/validate-artifact.py file.html` |
| Find hand-authored artifacts in a tree | `find . -name '*.html' -exec grep -L '<!-- assembled by' {} \;` |
| Confirm theme-toggle present | `grep -E '\[data-theme-toggle\]\|class="theme-toggle"' file.html` |

Run the validator before declaring any artifact done. The grep is for the impatient — the validator is the gate.

---

## Failure Mode (Real Example)

The SIEM deck regression is why this enforcement exists.

| Symptom | Root cause |
|---|---|
| Theme-toggle absent from rendered deck | Hand-authored HTML, never went through assembler, never got the auto-injected toggle component |
| PDF clipped 4 of 9 slides | Print CSS was patched inline using `overflow: hidden` on a fixed-height box smaller than the live viewport. Real `templates/print/deck-print.css` uses 1:1 dimensions. |
| User couldn't switch to light mode for the printout | No toggle to switch with. The deck shipped dark-only. |
| Validator didn't catch it (at the time) | The marker check and theme-toggle check did not exist yet. |

The skill upgrade — assembler marker, auto theme-toggle, validator gates, per-shape print CSS — exists because of this regression. Don't reintroduce it.

---

## Override Flag (Rare)

```bash
python3 scripts/assemble-template.py --shape deck --theme dark-focus --no-theme-toggle
```

| When to use | When NOT to use |
|---|---|
| The artifact is a single screenshot-target (no live HTML viewer) | "I forgot to include it" |
| The shape is `editor` or `custom-editor` and toggle conflicts with editor chrome | "The user didn't ask for one" — they did, by default |
| Embedded into a host page that already provides a toggle | "It's a quick draft" — quick drafts get toggles too |

The flag exists for narrow legitimate cases. If you reach for it, justify it in the artifact's `<!-- generated-with -->` comment so future readers know why.

---

## TL;DR

Run the assembler. Trust the marker. Trust the validator. Hand-authoring is how the SIEM deck shipped broken — don't repeat it.
