# Vision walkthrough: the application spine on fixtures

The checkpoint script (frontend-first method, step c). Walk it in order;
every step works today against the seeded demo register at
`http://localhost:6300/#/w/ws-demo/b/risk`. What is real: every row write
(form submit, transition, approval effect) goes through the actual API and
permission evaluator. What is fixture: the workflow/form/recipe
*definitions*, pending tasks, and activity history — every surface showing
them wears a small "engine preview" pill. Start as `risk@unops.org` (the
sidebar's persona switch, bottom-left).

## The walk

1. **The register lands as an app, not a grid.** Open the risk register.
   You arrive on the **Overview**: what this app is for (the purpose
   hero), **Report a risk** as the primary act, real state counts on
   tiles with the distribution bar ("includes N withheld" in the
   governance colour — the totals are honest), *Needs attention* (longest
   unreviewed, largest exposure — real sorted queries), *Waiting on you*,
   and *While you were away*. The view tabs — Overview · Table ·
   Automations · Fields — are the app's map. The grid is the **Table**
   tab: one click away, never the front door. *(This step exists because
   the first cut landed on the grid and the owner rejected it — the
   correction the checkpoint is for.)*

2. **Intake with line items** (FM-1..3, FM-7). Click *Report a risk*. Note
   what makes it intake rather than a contact form: sections with intent,
   help written in a colleague's voice, **Mitigation actions** as
   repeatable line items, and the footer stating exactly where the row
   lands (*"Lands as Open, assigned for triage"*). Fill Risk + Owner, add
   one mitigation line, submit. The dialog closes, the grid scrolls to
   your row and flashes it — a real row, written on the `form` channel.

3. **The state is a doorway, not a cell** (AU-10). Click your new row's
   Status cell. No text overlay opens — the detail panel does, with the
   **workflow panel** on top: current state as a chip, and the doorways
   out of it. *Start mitigation* is open; *Close without mitigation* wears
   a plum **Risk team** gate; where its condition fails, the doorway is
   shut with the reason under it, not hidden.

4. **A direct transition is a real write.** Take *Start mitigation*. The
   chip flips to Mitigating, the grid refetches, and the Status column
   agrees — that write went through the same evaluator as every grid edit.

5. **A gate raises a task** (AU-4, AU-15). Take *Close risk*. Nothing is
   written; the panel says the request now waits on Risk team. Open the
   **Inbox**: your request is there — and its Approve button is **dead for
   you**, with the reason beside it: *you raised this, and the gate does
   not allow self-approval.* Switch persona to `dev@unops.org`? Then the
   seeded task (raised by dev@) is dead instead — the block follows the
   identity, not the button.

6. **The decision performs the transition.** As the other persona (or on
   the seeded task), Approve. The state write happens under the
   *decider's* identity — check the row's Status in the grid.

7. **Activity is a story with attribution** (PM-7, PM-9, PM-10). On any
   row, detail panel → **Activity** tab. Read downward: your transition
   (channel `api`), a change by a **recipe** (attributed in the automation
   colour), an edit to a restricted field — *changed (value withheld)*,
   because the drawer is trimmed by the same Decision as the grid — and a
   governance event for a rule change.

8. **Automations are sentences** (AU-1, AU-14, AU-16). Header →
   *Automations*. Each recipe is an English sentence whose parameters are
   typed chips — fields, values, principals, states in their own role
   colours — and *Schedule the next review* carries two `today()`-style
   **expression** parameters in code dress: that is AU-16, visible. Below,
   the gallery: adopting a template copies the record into the register.
   No canvas, no flowchart, anywhere.

9. **The extension feels native** (BP-28). Back on a row's Fields tab,
   scroll down: **Board attention** and **Review cadence** read as
   ordinary fields with a quiet *· extension* note (hover it), and the
   **Decision log** renders as an extension collection — the locked base
   plus workspace additions, felt as "I added columns".

10. **Three themes.** Flip light / grey / dark in the header. Every spine
    surface follows — no colour in the spine is a literal.

11. **A record is a document, and the app is multiple tables** (GR-17,
    BP-8 — the composition that makes it an app rather than a grid with
    chrome). From the Overview, click any *Needs attention* row: it opens
    as a **record page** — breadcrumb, the fields as a form (the withheld
    treatment intact), and the child collections as REAL TABLES INLINE:
    Mitigation actions with their own state chips, the Decision log as a
    BP-28 extension table, workflow and activity on the rail. Then use
    the app nav: **Mitigation actions** is a page of its own — every
    action across all risks, flat, each row linking back to its record.
    The nav reads Overview · Risks · Mitigation actions, never "Table".
    (Parent rows are real; child rows are fixture-derived per parent
    until BP-5/FM-3 children are served.)

12. **The same rows, morphing** (GR-13..16). On the Table tab, use the
    view switcher: **Board** (cards in state lanes — click one, the
    workflow panel opens), **Calendar** (by Last reviewed, landing on the
    busiest month), **Gantt** (mitigation windows as bars in state
    colours, real dates, months scaled). Same fetch, same filter, same
    withheld annotation above all of them — the views morph, the
    governance does not. A view whose field map is missing names the
    missing fields instead of rendering blank.

13. **Make your own app** — the finale. Sidebar → **New app**. Describe
    what you track in a sentence (try "Track partner MOUs with an owner,
    amount and renewal date") — or adopt one of the four organizational
    templates (contract, asset, project, fleet — with their states,
    automations and extension notes visible before you commit). Either
    way you land on **"Here is your app — check it before it exists"**:
    rename fields, remove them, add one, read the state flow and starter
    automations. Create it. It appears in the sidebar and opens as an
    app — purpose hero, zero-count state tiles, the model you reviewed —
    not as a config screen. (Session-lived: the persistence engine is
    what the checkpoint gates.)

## The question this walk answers

Does a register with intake, state, gated approvals, legible automations
and honest history *feel like the product you have in mind* — before any
engine is built? Whatever the answer changes goes back into the fixtures
(cheap) rather than into engines (expensive). If the answer is yes, the
engines at roadmap Next #1 replace the fixtures shape-for-shape.

## Known seams (deliberate, this stage)

- Pending tasks, recipe toggles and captured line items reset on reload —
  the store is session-lived until the engines land.
- The seeded approval task performs no write when approved (it references
  no real row); tasks raised live from a transition do.
- Line items from intake render in the row detail marked *from intake ·
  engine preview*; child collections persist for real when FM-3's server
  path lands.
- The activity history behind each row is scripted except for what you do
  in the session, which is prepended live.
