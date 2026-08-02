# Monday.com Enterprise — product profile

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session:
> - https://monday.com/w/enterprise (fetched 2026-08-02)
> - https://monday.com/pricing (fetched 2026-08-02) — EUR prices, annual-billing basis noted per row
> - https://monday.com/whats-new (fetched 2026-08-02) — latest page only, not full history
> - https://monday.com/w/ai (fetched 2026-08-02)
> - https://monday.com/w/app-developers (fetched 2026-08-02)
> - https://developer.monday.com/apps/docs/intro (fetched 2026-08-02)
> - https://developer.monday.com/api-reference/reference/audit-event-catalogue (fetched 2026-08-02)
> - WebSearch result snippets citing named support.monday.com articles (see caveat)
> Shelf life: pricing/changelog claims stale after ~1 quarter.

**Evidence caveat, stated up front:** `support.monday.com` (the docs/help
center, where the deepest feature evidence lives) returns HTTP 403 to direct
fetches this session. Claims sourced from it come via search-result snippets
that quote specific named support articles. Those rows are tagged
`[verified-snippet]` — weaker than a first-hand docs read, stronger than
marketing copy. `monday.com/whats-new` and `developer.monday.com` fetched
fine and are first-hand.

## Summary

monday.com (NASDAQ: MNDY, Tel Aviv/NYC, ~250K customers claimed) sells a
"work OS": a board-centric platform packaged as four products on one
substrate — monday work management, monday CRM, monday dev, monday service.
GTM is self-serve at the bottom (Free/Basic/Standard/Pro, credit-card
checkout) and sales-led at the top (Enterprise, custom pricing). The 2026
positioning is explicitly AI-first: "AI-enabled work platform", agents as a
"digital workforce". Enterprise is where the governance surface lives:
nearly every security, permission, audit and standardization feature is
gated to the Enterprise tier. [verified — monday.com/w/enterprise,
monday.com/pricing]

## Positioning statement (extracted, not invented)

For large organizations that need to "make strategic decisions with
confidence", monday.com for Enterprise is an AI-enabled work platform that
connects strategy to execution with "flexible yet standardized" no-code
workflows. Unlike rigid enterprise tools, it is "like water. It'll take its
shape and wrap around whatever you need it to do" (customer quote, Zippo).
Source: https://monday.com/w/enterprise. [marketing]

## Claimed USP (verbatim quotes)

- "Built for teams and agents working together" — monday.com/w/enterprise [marketing]
- "Flexible yet standardized" via a "no-code, drag-and-drop interface" — monday.com/w/enterprise [marketing]
- "6,970 hours saved per month" and "40% improvement in cross-team collaboration" — monday.com/w/enterprise [marketing]
- "61% of Fortune 500 companies" and "250K+ customers worldwide" — monday.com/w/app-developers [marketing]
- Motorola "346% ROI over 3 years" — monday.com/w/enterprise [marketing]

## Feature inventory

| Area | Feature | Evidence | Source |
|---|---|---|---|
| Platform model | Boards → workdocs → dashboards → portfolio, packaged as 4 products (WM, CRM, dev, service) on one substrate | [verified] enterprise page + pricing page list all four with separate tiering | monday.com/w/enterprise, monday.com/pricing |
| Grid/board | Board with groups, items, subitems, 30+ column types; views (table, kanban, Gantt, calendar, timeline) | [verified] pricing gating names timeline/Gantt at Standard | monday.com/pricing |
| Scale | 10,000 items/board (standard plans); 100,000 (Enterprise); mondayDB 3.0 roadmap: 1M then 10M items | [verified-snippet] support article "Item and subitem limits per board", "mondayDB 3.0" | support.monday.com/hc/en-us/articles/4404058746642, /35729781370130 |
| Automation | Recipe model: trigger + condition + action(s), sentence-style builder, prebuilt + custom recipes, unlimited recipes but metered actions | [verified-snippet] "Get started with monday automations" | support.monday.com/hc/en-us/articles/360001222900 |
| Automation | Action metering: 250/month (Standard), 25,000 (Pro), 250,000 automation+integration actions (Enterprise); only executed actions count | [verified] pricing page + [verified-snippet] rate-limits article | monday.com/pricing, support.monday.com/hc/en-us/articles/9060097050258 |
| Workflow | AI workflow builder: workspace-level, cross-board, flowchart with branches/conditions/wait, 7 AI action blocks; distinct from per-board recipes | [verified-snippet] "Comparing the workflow builder and automations", "AI Workflows: features and capabilities" | support.monday.com/hc/en-us/articles/18382067611410, /20598895919122 |
| Workflow | MCP Block: call any 3rd-party app with a public MCP server from a workflow (Jul 16, 2026); manage automations via Sidekick/MCP without UI (Jul 9, 2026) | [verified] whats-new page | monday.com/whats-new |
| Permissions | Layered model: account → workspace → board → column → item | [verified] enterprise page ("multi-level permissions across accounts, workspaces, boards, and columns") | monday.com/w/enterprise |
| Permissions | Board roles (Enterprise): Owner, Editor, Contributor, Assigned contributor, Viewer + granular per-category customization (Items, Subitems, Updates, Columns, Groups, Views, Forms) | [verified-snippet] "Board permissions on Enterprise", "Granular board permissions" | support.monday.com/hc/en-us/articles/31152393208466, /23717503216530 |
| Permissions | Item-level permissions: visibility controlled by designated People columns; "only edit assigned content" — Enterprise only | [verified-snippet] item-permissions articles; column restrictions are Pro+ | support.monday.com column/item permission articles |
| Permissions | Custom roles for account-level admin delegation (Enterprise) | [verified-snippet] "Custom roles for account permissions" | support.monday.com/hc/en-us/articles/8292728458386 |
| Governance | Managed templates: master template → instances (up to 1,000/template, May 2026), publish pushes changes to instances; 20 included per Enterprise account, more is a paid add-on; creation gated by account permission | [verified-snippet + verified] "Managed templates" article + whats-new | support.monday.com/hc/en-us/articles/18229256953234, monday.com/whats-new |
| Governance | Managed columns: centrally defined column editable only from the template (Enterprise); label cleanup shipped May 2026 | [verified-snippet + verified] | support.monday.com, monday.com/whats-new |
| Governance | Data Validation Rules across item lifecycle (May 17, 2026) | [verified] whats-new | monday.com/whats-new |
| Security | Tenant-level encryption with BYOK; multiple SSO vendors; SCIM provisioning (Enterprise); IP restrictions; HIPAA (CRM Ultimate) | [verified] enterprise page; [verified-snippet] SCIM/tier gating | monday.com/w/enterprise, stitchflow.com/scim/monday-com |
| Audit | Audit Log API (Enterprise, admins only): REST, 50 req/min, SIEM export, Splunk add-on; `audit_event_catalogue` query | [verified] developer.monday.com audit-event-catalogue + Splunkbase app 6483 | developer.monday.com/api-reference/reference/audit-event-catalogue |
| Audit | Scope is security/admin events (logins, exports, permission changes) — not item-level data change deltas | [verified] catalogue page describes "security-related activities" | developer.monday.com/api-reference/reference/audit-event-catalogue |
| Admin | AI Admin Usage dashboard: AI spend per user/feature/team (May 2026) | [verified] whats-new | monday.com/whats-new |
| Portfolio | Portfolio management solution (GA Jul 2024): portfolio↔project drill-down, intake board, template-based provisioning, AI portfolio risk insights | [verified] monday.com IR press release + coverage | ir.monday.com (Jul 31, 2024 release) |
| Resource mgmt | Capacity Manager, Resource Directory, Resource Planner (Aug 3, 2025) | [verified] whats-new | monday.com/whats-new |
| Apps | Apps framework: board/item views, dashboard widgets, custom objects, integrations, AI features, workspace templates; private/public/marketplace distribution with review | [verified] developer docs | developer.monday.com/apps/docs/intro |
| Apps | Marketplace: 850+ live apps, 1.6M installs, 87% of enterprise accounts have ≥1 app; revenue share after $200K lifetime revenue | [verified] app-developers page (their own numbers) | monday.com/w/app-developers |
| AI | Sidekick assistant; Agent builder ("digital workers"); prebuilt research/reporting/insights agents; simulation mode; agent activity logs; per-team AI spend limits; credits-based pricing | [verified] AI page (capabilities listed; depth untested) | monday.com/w/ai |
| AI | Sidekick Skills Marketplace (Mar 30, 2026); monday vibe app-building with per-role creation permissions (May 2026) | [verified] whats-new | monday.com/whats-new |
| API | GraphQL API; metered per tier: 1K calls/day (Standard), 10K (Pro), 25K (Enterprise) | [verified] pricing page | monday.com/pricing |
| Docs | Workdocs (collaborative docs connected to boards) | [verified] pricing page (Docs counted in Free tier limits) | monday.com/pricing |

## Pricing & packaging

monday work management, EUR, per seat, **annual billing** (18% discount vs
monthly), fetched 2026-08-02:

| Tier | Price (annual basis) | Gating highlights |
|---|---|---|
| Free | €0, 2 seats | 3 boards, 8 column types |
| Basic | €9/seat/mo | unlimited items/viewers, 1,000 AI credits/mo |
| Standard | €12/seat/mo | 250 automation actions/mo, Gantt/timeline, guests, 1K API calls/day |
| Pro | €19/seat/mo | 25K automation actions/mo, private boards, column permissions, 10K API calls/day |
| Enterprise | Custom (sales-led) | 250K automation+integration actions/mo, multi-level + item permissions, board roles, audit log API, SCIM/SSO, BYOK, managed templates/columns, portfolio + resource mgmt, 25K API calls/day, 99.9% SLA |

Third-party reporting (not confirmable from monday.com): Enterprise
reportedly ~$52/seat/mo list in early 2025, negotiated $15–18/seat at 50–200
seats [marketing — vendr/plaky-class sources via search]. CRM, dev, and
service carry separate, higher tiering (service Pro €45/seat/mo).

The packaging pattern to notice: **governance is the upsell**. Permissions
depth, audit, standardization, and identity management are all Enterprise
gates; automation and API are metered quantities at every tier.

## Trajectory (from monday.com/whats-new, last ~12 months; single page, not full history)

- **AI agents into the core loop**: MCP Block for AI Workflows (Jul 16, 2026); automations manageable via Sidekick/MCP without UI (Jul 9, 2026); Sidekick Skills Marketplace (Mar 30, 2026). [verified]
- **Governed standardization deepening**: Data Validation Rules, managed-template instances to 1,000, managed-column label cleanup (all May 17, 2026). [verified]
- **AI cost governance for admins**: AI Admin Usage dashboard tracking spend per user/feature/team (May 17, 2026). [verified]
- **App-building for non-developers**: monday vibe creation permissions by role (May 17, 2026), dedicated URLs for vibe apps (Jan 2026 per third-party roundup). [verified / verified-snippet]
- **Resource management buildout**: Capacity Manager, Resource Directory, Resource Planner (Aug 3, 2025). [verified]
- **Scale**: mondayDB 3.0 targeting 1M then 10M items/board. [verified-snippet]
