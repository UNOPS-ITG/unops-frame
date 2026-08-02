# Discovery scope: Smartsheet + Frappe + Monday.com

Date: 2026-08-02. Pipeline: `/product-discovery` (full run, three competitors,
per-competitor research parallelized).

## Products under research

| Product | Slug | Why it is on the list |
|---|---|---|
| Smartsheet (https://www.smartsheet.com/) | `smartsheet` | The grid-first incumbent Frame's vision explicitly benchmarks against ("Smartsheet-grade grid"). Sets the bar for what operations officers like Maya expect from day one: grid ergonomics, view morphing, forms, dashboards, proofing/approvals at enterprise scale. |
| Frappe Framework (https://frappe.io/framework, repo https://github.com/frappe/frappe) | `frappe` | The metadata-driven architecture Frame's Blueprint engine is modeled on ("Frappe-style, metadata-defined Blueprints"). Open source — the one competitor whose actual implementation we can read. The comparison tests whether Frame's "zero per-Blueprint code" claim matches or beats the DocType system's depth (permissions, workflow, versioning, customization). |
| Monday.com Enterprise (https://monday.com/w/enterprise) | `monday` | The work-OS platform play: boards → apps → portfolio, with an enterprise tier (security, governance, admin controls) aimed at exactly the buyer Frame's steward/governance story addresses. Strongest of the three at packaging automations and composed apps for non-technical builders. |

Together they triangulate Frame's positioning: Smartsheet is the *grid*
benchmark, Frappe is the *metadata engine* benchmark, Monday is the
*platform/governance packaging* benchmark.

## The question

Full-product comparison, all three — not a single feature area. Each analysis
should still weight the ground its competitor is strongest on (per the table
above), since that is where the evidence is richest and Frame's gaps most
consequential.

## The decision this informs

What Frame should build next — ending in a Frame PRD (new or amended) in
`specs/frame-prds/`, slotted into the roadmap. Sharper framing: Frame's
vision already commits to a Smartsheet-grade grid over Frappe-style
metadata; this run tests that synthesis against the real products and finds
where the *combination* leaves open ground neither incumbent covers (e.g.
governed promotion, ABAC transparency, warehouse-native corporate data).

## Frame context for researchers

- Vision: `specs/frame-prds/product-vision-frame.md`; index and shared
  definitions: `specs/frame-prds/00-prd-index.md`.
- PRD modules an opportunity may land in: 01 Blueprint Engine (BP-*),
  02 Grid and Views (GR-*), 03 Forms and Intake (FM-*), 04 Automation and
  Workflow (AU-*), 05 Permissions and Security (PM-*), 06 Reporting/
  Dashboards/Prism (RP-*), 07 Document Generation (DG-*), 08 AI Layer,
  09 Integrations, 10 App Composer, 12 Notifications, 13 Search (SR-*),
  14 Corporate Data.
- Non-goals that bound opportunities: no seat-licence-driven sharing model
  (external participation is forms + magic links in v1), single-tenant
  workspaces, nothing on GCP without owner consent, no per-Blueprint code.

## Optional inputs

- No raw user research / pilot feedback supplied — no `synthesize-research`
  pass this run.
- No existing PRD designated for amendment up front; `write-prd`'s
  amend-before-create rule decides at phase 4.
