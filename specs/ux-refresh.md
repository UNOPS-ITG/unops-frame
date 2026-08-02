# The UX refresh — compiled refactor backlog

Compiled from two independent reviews of the running product (2026-08-02): a visual
identity review (`frontend-design` skill) and an interaction-craft critique
(`interface-craft` skill), both fed the product vision, the feature inventory, and 16
screenshots of every live surface. Source material in `.artifacts/ux-review/`.

The shared diagnosis, one sentence each:

- **Visual**: the product is *correct everywhere and designed nowhere* — no fonts are
  actually loaded, one hue is spread evenly over everything, all text is the same size,
  and there is no surface depth, so every screen reads as a wireframe.
- **Interaction**: the product *talks about itself instead of the user's work* — prose
  where affordances should be, no focusing mechanism on any screen, no feedback for any
  action, and the three signals that make a grid feel like a grid (frozen primary
  column, row numbers, type-to-add) are all missing.

The refresh keeps the token system as the design system — every change below is
expressed *through* `brand-tokens.css`, never around it. The fitness suite still
gates literals.

---

## Tier 1 — Foundation (everything else inherits these)

**U1. Load the typefaces.** `index.html` loads no fonts; every declared family falls
through to the OS default. Self-host a characterful grotesk for display and UI
(distinctive, not Inter) plus JetBrains Mono (already tokened, already used for field
ids), with `font-display: swap` and preload. Then actually *use* the scale: page titles
`2xl/650/tight`, section labels `xs/wider/uppercase`, all numerics `tabular-nums`.

**U2. The ink shell.** Rename the layout metaphor to match the product's name: a
permanently dark navy-ink sidebar + header band (drawn from the existing dark-theme
ramp) framing a bright content well, in all three themes. Active nav = cyan pill on
ink. Cyan stops being wallpaper and starts being the accent it was designed to be.

**U3. Assign the palette roles.** Six accent families exist and none are used. Fix the
role map once, in tokens: status (open=ocean, mitigating=amber, closed=neutral),
governance/withheld = cherry/plum family, corporate data = teal, primary action +
selection = cyan. Nothing else gets colour, which is what makes these legible.

**U4. Surface depth.** Cards and dialogs get real `--shadow-sm/md` + brand-tinted
1px borders; the toolbar gets a soft shadow separating it from the well; white-on-white
pages (workspace, corporate, fields) get a barely-there radial brand tint. The grid
gets none of this — density and quiet are its atmosphere.

## Tier 2 — The grid becomes a grid (the "80% as good as Smartsheet" risk, addressed)

**U5. Frozen primary column + row numbers.** The title column must never scroll away
(Glide `freezeColumns` + a row-marker column). The largest single gap vs. Smartsheet.

**U6. Ghost "type to add" row.** A permanent affordance row at the grid's bottom;
typing into it creates through the one write path and keeps focus for the next row.
The New-row dialog remains for the guided case.

**U7. Status as chips, in-canvas.** Custom cell renderer: dot + tint chip per status
option (role colours from U3), resolved through the theme resolver like every other
canvas colour.

**U8. Withheld as material.** Withheld cells get the tinted diagonal hatch (token
already exists) so withheld ≠ empty at a glance; the column-stub padlock stays. The
"N withheld" chip becomes cherry-tinted, with a click-popover: "20 rows above your
clearance are counted but not shown. Exports say so too."

**U9. Row-created feedback.** After create (dialog or ghost row): scroll to the new
row, tinted flash-fade ~800ms, selection lands on it. Import commit gets a count-up
beat; filter apply pulses the annotation chip once. These three moments are the entire
animation budget, storyboarded with named timings; nothing else moves.

**U10. Grid comfort details.** Row hover highlight, ISO/locale dates (a "1/2/2026"
in a UN org is genuinely ambiguous), right-aligned tabular numerics, fix the floating
"·" stale mark (proper glyph inside the corporate chip), corporate references rendered
as teal key-chips rather than bare text.

## Tier 3 — Every page gets a focal point

**U11. Register header as a designed object.** Blueprint name in display type; tier +
version as quiet badges; stat chips (rows · withheld · views); toolbar grouped into
[view/filter] | [create] | [data in/out] | [inspect] with separators; New row stays the
one filled primary.

**U12. Workspace as launcher, not apology.** Greeting-scale headline, register cards
with presence (tinted icon tile, row/withheld counts, last activity), a dashed
"New register" affordance card, and the architecture prose demoted to a footnote
popover. Same treatment for every empty state: headline + one sentence + one verb.

**U13. Catalogue grouped by business domain.** 556 identical cards become 8 domain
sections (PCG, IPMG, ITG… — the data is already on every relation) with counts, search
within, and disclosure as a *filter* rather than 556 identical "entitled" chips.
Expansion becomes a side panel (not in-grid growth that stretches siblings); the raw
probe dump is replaced by one human sentence + a "Why?" disclosure that shows the
diagnostics; kill the mojibake by sanitising descriptions at sweep time.

**U14. Dialog craft.** Ink header band on New-row and picker; "required"/"restricted"
as chips; the corporate field in the New-row form becomes an anchored popover combobox
instead of a modal-over-modal; the picker's "Resolved in your own context" footer set
in teal with a key glyph — it is a feature, not fine print.

**U15. Chrome quarantine.** Dev persona switch becomes a dashed amber "dev" pill
menu; theme switch becomes an icon menu; both leave the masthead's prime real estate.
Sidebar earns its width (saved views nested under each register, recents) or collapses
to icons.

## Tier 4 — Polish and hygiene

**U16.** Copy pass: "Import 1 rows" → pluralise; de-doctrine every notice to one
sentence with a "Learn more" popover; catalogue fixture card stops saying
"(development fixture)" in user-facing copy (mark it via a chip instead).
**U17.** Seed-data hygiene: remove `E2E 17856…` litter rows from the demo register
(test rows should clean up after themselves).
**U18.** Focus-visible audit across the new components; the aria mirror keeps parity
with the new visual states (chips announce their meaning, hatch announces "withheld").
**U19.** Fitness additions: a check that `index.html` preloads the declared families
(fonts can never silently vanish again), and a check that status/governance colours
come from the role tokens, not ad-hoc accents.

## Sequencing note

Tier 1 first — it changes every screenshot and costs the least. Tier 2 before Tier 3:
the grid is the product, and the register is where the Smartsheet comparison is won or
lost. U5–U8 are pure-code (no design debate); U11–U13 benefit from a look at Tier 1's
result before committing.

## What we deliberately do not do

No purple gradients, no glassmorphism, no decoration on the grid surface, no second
component library, no animation outside the three storyboarded moments, and nothing
that moves colour or width decisions out of `brand-tokens.css`.
