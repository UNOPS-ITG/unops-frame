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

1. **The register is the front door.** Open the risk register. The grid is
   unchanged — chips in the Status column, 200 rows, "20 withheld" in the
   governance colour. The spine adds three quiet things: **Report a risk**
   beside New row, **Automations** in the header, **Inbox (2)** in the
   sidebar.

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
