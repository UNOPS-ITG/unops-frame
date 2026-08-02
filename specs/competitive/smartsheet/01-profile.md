# Smartsheet — product profile

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session (all 2026-08-02):
> - https://www.smartsheet.com/pricing (SPA; price strings concatenated — see caveat below)
> - https://help.smartsheet.com/ (docs index)
> - https://help.smartsheet.com/articles/506775-system-requirements-for-using-smartsheet
> - https://help.smartsheet.com/articles/2483463-large-scale-sheets-table-view
> - https://help.smartsheet.com/articles/765715-grid-gantt-calendar-and-card-views
> - https://help.smartsheet.com/articles/2481701-use-conditional-logic-to-streamline-form-submissions
> - https://help.smartsheet.com/articles/2482509-collaborate-on-proof
> - https://help.smartsheet.com/articles/2482646-create-cross-sheet-references
> - https://help.smartsheet.com/articles/2482785-datamesh-faq
> - https://www.smartsheet.com/content-center/product-news/release-notes (latest page only; changelog paginates)
> - https://www.smartsheet.com/content-center/product-insights/product-updates/powering-future-work-next-generation-platform
> - WebSearch result snippets (citable, listed inline): community.smartsheet.com limit threads; help.smartsheet.com automation/report/sharing articles; smartsheet.com Contributor-seat and MCP GA announcements; businesswire.com 2026-06-11 MCP press release; tech.co / costbench.com / spendhound.com 2026 pricing pages; g2.com review snippets
> Shelf life: pricing/changelog claims stale after ~1 quarter.

## Evidence-quality caveats (read first)

- **The pricing page is an SPA and WebFetch returned concatenated price strings** ("$129", "$2419" for both billing bases — impossible). The corrected figures below come from three independent 2026 pricing trackers surfaced by WebSearch (tech.co, costbench.com, spendhound.com), which agree with each other and decompose cleanly into the concatenated strings ($12|$9, $24|$19). Tier *names*, seat definitions and feature gating rows fetched from the pricing page itself are reliable.
- The help-centre URL for sheet approval workflows redirected to **Brandfolder** approval docs; sheet-approval claims below rest on search snippets of help articles 2479276 and 2476191, not a full article fetch.
- g2.com blocks direct fetch; review evidence is search-snippet level.
- Only the latest release-notes page was fetched; trajectory bullets cover roughly Mar–Jul 2026, not a full 12 months.

## Summary

Smartsheet (Bellevue, WA; founded 2005; taken private by Blackstone/Vista in a
$8.4B deal completed January 2025 — widely reported, not re-verified this
session) is the grid-first enterprise work management incumbent: a
spreadsheet-shaped surface (sheets of rows/columns) with project views,
forms, dashboards, automations and a large premium-app layer (Control Center,
DataMesh, Dynamic View, Data Shuttle, Bridge, DataTable, WorkApps) sold on
top. GTM is self-serve at Pro/Business and sales-led at Enterprise and for
every premium app. It is currently mid-way through a re-platforming: the
legacy grid is being superseded by **table view** (autosave, real-time
collaboration, 50k rows / 1M cells on Enterprise), with board and timeline as
the other next-gen views [verified — help 2483463, next-gen platform
announcement].

## Positioning statement (extracted, not invented)

For enterprise teams who need to manage projects, programs and processes at
scale, Smartsheet is an enterprise work management platform that combines
spreadsheet familiarity with project views, automation, and enterprise-grade
security; unlike lightweight PM tools, it scales to portfolio level via
premium applications. (Synthesized from smartsheet.com/platform/features and
the next-generation-platform announcement; Smartsheet's own current tagline
territory is "the enterprise work management platform".)

## Claimed USP (verbatim quotes)

- Table view: "faster load and calculation performance, continuous save and
  refresh for real-time collaboration" — help.smartsheet.com/articles/765715 [verified]
- "All views are synchronized from the same data source, so updates to one
  view are instantly reflected across all views" — help.smartsheet.com (views topic) [verified]
- Next-gen platform: supports "up to 50,000 rows and 1 million cells" with
  "plans to scale to 100,000 rows and beyond"; formula references increased
  "10x" — next-generation-platform announcement [marketing — the 50k/1M half is
  verified in help 2483463; the 100k+ and "10x" halves are roadmap copy]
- Proofing: "You can invite anyone with a valid email address to review your
  proof, including users or people outside of your organization" — help 2482509 [verified]

## Feature inventory

| Area | Feature | Evidence | Source |
|---|---|---|---|
| Grid | Legacy grid view: 20,000 rows / 400 cols / 500,000 cells per sheet; 4,000 chars/cell; manual save model | [verified] | help 506775 |
| Grid | Table view (next-gen grid): autosave, real-time updates, personal sort, improved filters; Enterprise large-scale opt-in raises limits to 50,000 rows / 1M cells | [verified] | help 765715, 2483463 |
| Grid | Large-scale sheets (>20k rows / >500k cells) **disable**: grid view, automated workflows (mostly), Bridge, Salesforce/Jira connectors, DataMesh, reports, form creation/editing, mobile apps, ODBC, Pivot, portfolio provisioning, proofs, Resource Management, search, work insights, and the public API; forms can still render/submit; some change-triggered workflows with a short action list are supported | [verified] | help 2483463 |
| Grid | Row hierarchy: indent/outdent (Ctrl+]/[), unlimited depth, children drag with parent, hierarchy formulas (CHILDREN/PARENT/ANCESTORS) | [verified] | help 504734, 2476811 (snippets) |
| Grid | Paste limit 500 rows at a time; >5,000-row sheets lose several connectors (Bridge, Tableau, PowerBI, Zapier, Calendar App…) | [verified] | help 2482601, 506775 |
| Views | Grid, Gantt, card, board, calendar, timeline, table; instant switching, views synchronized | [verified] | help 765715 |
| Views | Gantt: needs 2 non-formula date columns + project settings; dependencies, critical path | [verified] | help 765715 |
| Views | Timeline view is Business+ only; card view needs a single-select/contact column | [verified] | help 765715 |
| Formulas | Cell-anchored formulas anywhere; cross-sheet references capped at **100 distinct references per sheet**, 100,000 inbound cells per range; broken refs return #INVALID REF | [verified] | help 2482644/2482646, community 127183 |
| Formulas | Cell links: 500,000 in/outbound per sheet (100,000 Gov); community threads document links breaking/staleness in Control Center estates | [verified] | help 506775, community 98919/100822 |
| Forms | Form builder per sheet; conditional logic (When/Then, nested cascades) — **Business+ only**; logic-size limit per source field | [verified] | help 2481701 |
| Forms | Update requests can go to any email address, even unshared users | [verified] | help 2479266 (snippet) |
| Forms | Forms create one row; no child/line-item sections (no column type creates child records — confirmed by absence across forms docs) | [verified by absence] | help forms topic |
| Automation | Rule automations: alerts, update/approval requests, assign, change cell, move/copy row, record date, lock rows; limits: 150 workflows/sheet, 100 blocks/workflow, 30 action blocks | [verified] | help 2476191 + snippets |
| Automation | Approval requests pause workflow until approved/declined; multi-step approval paths; responses recorded in sheet | [verified — snippet level] | help 2479276 |
| Automation | Pro plan: 250 automations/month; Business+: unlimited | [verified] | pricing page |
| Proofing | Image/video/document/PDF proofs, versioning (responses stay with version), annotations, external reviewers without licenses; Business+ | [verified] | help 2482509, pricing |
| Dashboards | Widgets: metric, chart, report, rich text, image, title, web content; Pro capped at 10 widgets/dashboard | [verified] | help 518558 (snippets), pricing |
| Reports | Row reports across up to 30,000 source sheets; grouping w/ aggregates; auto-collapse above 2,500 rows; reports can't source other reports | [verified] | help 2482078/2482079/2482082 (snippets) |
| Sharing | Item/workspace sharing at 5 levels: Owner, Admin, Editor, Commenter, Viewer; no native row- or field-level granularity | [verified] | help 1155182/2483288 (snippets) |
| Sharing | Contributor seat (GA Apr 2026): free internal seat — view, comment, attach, respond to update requests, submit forms, use shared views | [verified] | smartsheet.com Contributor-seat GA post |
| Premium apps | Dynamic View: row/field-level view+edit access without sharing the sheet (the row/field permission answer, sold separately, Business+) | [verified] | help 2477821/2478391 |
| Premium apps | Control Center: portfolio provisioning from templates; Global Updates push schema changes to provisioned copies | [verified — index level] | help centre index |
| Premium apps | DataMesh: copies/syncs data between sheets ("Copy Data", "Copy and Add", scheduled); 190 mapped columns/workflow; Advanced Work Management plan; explicitly a copy mechanism | [verified] | help 2482785 |
| Premium apps | DataTable: up to 2M rows external store feeding sheets; Data Shuttle: ETL in/out; Bridge: cross-system orchestration; WorkApps: composed role-scoped apps (Enterprise incl.) | [verified — index/snippet level] | help centre index, search snippets |
| AI | Smart Assist (conversational, file upload GA Jul 2026), AI charts/dashboards editable from connected AI tools, formula generation (Enterprise), Smart Columns | [verified] | release notes, pricing page |
| AI | MCP server GA (Claude connector Mar 2026; ChatGPT, Copilot, Gemini Enterprise Jun 2026; US-first for ChatGPT/Copilot) | [verified] | smartsheet.com MCP GA + businesswire 2026-06-11 |
| API | REST API; Business+ only; report full-CRUD added Jul 2026; webhooks with custom headers Jun 2026; unavailable on large-scale sheets | [verified] | pricing, dev changelog via release notes, help 2483463 |
| Enterprise | SAML SSO + SCIM (Enterprise); Safeguard add-on: customer-managed encryption keys in AWS KMS — **sheet data only**, not attachments/reports/dashboards/WorkApps; regional instances (US, EU, Gov; DataMesh absent in Gov/AU) | [verified] | smartsheet.com security pages + CMEK datasheet (snippets), help 2482785 |

## Pricing & packaging

| Tier | Price (billing basis!) | Gating |
|---|---|---|
| Free | $0 | Very limited (per third-party trackers; not shown on main pricing page fetch) |
| Pro | **$9/member/mo billed annually; $12 billed monthly** [verified via three 2026 trackers; page fetch garbled] | 1–10 Members; unlimited Contributors; unlimited sheets/forms/reports; 250 automations/mo; 10 widgets/dashboard; **no API**; no conditional form logic; no proofing |
| Business | **$19/member/mo billed annually; $24 billed monthly** [same basis] | 3+ Members; unlimited Guests/Contributors; unlimited automations & widgets; conditional form logic; proofing; API; timeline view; eligible to buy premium apps |
| Enterprise | Custom, sales-led, 10+ Members | SSO/SCIM, AI formulas/text/charts, WorkApps, large-scale sheets (opt-in), Safeguard (CMEK) purchasable |
| Advanced Work Management | Custom | Bundles premium apps (DataMesh requires this tier or higher) |

Seat model: **Members** (paid, create/edit) vs **Contributors** (free internal:
view/comment/attach/forms/update requests) vs **Guests** (free external, can
edit and comment) [verified — pricing page + seat-types article]. Premium apps
are priced separately; third-party procurement data says they add 20–50% to
contract value [verified as claim by vendr.com snippet — treat as directional].

## Trajectory (from changelog + announcements, ~Mar–Jul 2026)

- **Re-platforming the grid**: table view is the successor surface — autosave,
  real-time, 50k rows/1M cells, saved-filter and sheet-size improvements
  landing weekly (Jul 22/27/31 release notes). Roadmap: 100k+ rows, "data
  links" for cross-sheet references, dynamic dropdowns [next-gen announcement].
- **AI everywhere**: Smart Assist file upload GA (Jul 17), AI-built/edited
  dashboards from connected AI tools (Jun 25), MCP connectors for Claude
  (Mar 2), Gemini (Jun 11), ChatGPT/Copilot (Jun 11).
- **Workspace scaffolding from natural language** (Jun 18): "build a
  structured workspace in minutes, just by describing what you need".
- **API/webhook maturation**: reports full CRUD (Jul 9), webhook custom
  headers (Jun 29), TLS hardening (Jul 6).
- **Seat-model loosening**: Contributor seat GA (Apr 30) — free commenting,
  attachments, forms, update requests — a distribution play to keep
  collaborators inside the tenancy without paying.

Reading: investment is concentrated exactly where Frame's vision attacks —
grid scale and AI access — but the large-scale mode still trades away most of
the platform (workflows, reports, forms editing, search, API) to get there,
and the semantic model (sheets of untyped cells, copy-based premium apps) is
unchanged.

## User sentiment (snippet-level)

- Community threads (Sep 2025 onward) report notable load/refresh performance
  regressions on the legacy grid [verified — community 142201/142360].
- Long-running complaints: cell links breaking or going stale in Control
  Center estates [community 98919, 100822]; the 100 cross-sheet reference cap
  as a hard consolidation blocker [community 127183, 139001].
- G2 2026 snippets: praise for flexibility/collaboration; complaints of steep
  learning curve and visual limitations [g2.com snippet].
