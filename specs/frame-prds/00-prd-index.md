# Frame PRD Set: Index and Shared Context

Version 0.1, August 2026. Companion to Product Vision: Frame v0.2.

## Document map

| # | PRD | Covers |
|---|-----|--------|
| 01 | Blueprint Engine | Metadata model, parent-child, versioning, provenance, promotion ladder, catalog |
| 02 | Grid and Views | The Frame grid, view morphing (Gantt, board, calendar), master-detail forms, saved views |
| 03 | Forms and Intake | Internal and external forms, conditional logic, child sections, intake routing |
| 04 | Automation and Workflow | Tier-one automations, event contract, Workflow Studio binding, graduation |
| 05 | Permissions and Security | ABAC evaluation, composition, transparency principle, audit, lifecycle |
| 06 | Reporting, Dashboards, and the Prism Handshake | Reports, dashboards, Postgres replication |
| 07 | Document Generation | Templates, merge, child iteration, e-signature, Drive filing |
| 08 | AI Layer | Native assists, Playbook delegation, MCP surface |
| 09 | Integrations | Google Workspace (incl. bound Sheets), Atlassian, webhooks, import/export |
| 10 | App Composer | Role-scoped composed applications |
| 11 | Grid Component Evaluation | Research, candidate analysis, recommendation, spike protocol |
| 12 | Notifications | Notification model, channels, preferences, digests, delivery pipeline, storm control |
| 13 | Search Architecture | Omnibox, index pipeline, two-stage permission trimming, engine selection |
| 14 | Corporate Data | Organizational master data and facts from the warehouse, discovered and resolved in the reader's own context |

## Shared definitions

**Blueprint.** A versioned metadata document defining a document type: fields, validation, relationships, children, permissions, workflow states, computed fields, view defaults, lifecycle policies, provenance.

**Row.** An instance of a Blueprint. Parent rows may own child rows in named child collections.

**Workspace.** A container owned by a team, holding Blueprints (personal and team tier), views, dashboards, automations, and a mapped Drive folder.

**Catalog.** The organization-wide registry of organizational-tier Blueprints, with credit lines, adoption stats, and stewardship metadata.

**View.** A saved, shareable rendering of a Blueprint's rows: grid, Gantt, board, calendar, or timeline, with filters, sorts, groupings, and column configuration. Views are permission-trimmed at render.

**Tier.** Blueprint governance level: personal, team, organizational.

**Steward.** The person or role accountable for a domain's organizational Blueprints and promotion decisions.

**Dimension.** Organizational master data held in the warehouse and discovered by Frame rather than authored in it: a keyed set of reference entities with a label, attributes and optionally a hierarchy — projects, countries, funds, business units, suppliers, positions. A Blueprint field binds to one; the row stores the key.

**Fact.** Transactional data in the warehouse at a declared grain, exposing measures Frame reads but never aggregates.

**Disclosure class.** Whether a dimension's values are disclosable to any authenticated staff member (`open`) or vary by principal (`entitled`), assigned by mechanical probe of the warehouse's own policies and never by assertion. It decides whether Frame may serve the dimension from its own projection or must resolve it live under the reader's credentials.

## Personas (shared across PRDs)

**Maya, operations officer.** Runs three trackers today in Sheets. Wants speed and zero training. Never opens the Blueprint editor.

**Daniel, team lead / power user.** Builds trackers for his unit, writes formulas and automations, submits Blueprints for promotion. Opens the Blueprint editor weekly.

**Ingrid, practice steward.** Reviews promotions, owns the vendor and risk domains in the catalog, enforces naming and data standards. Time-poor; the AI-assisted review exists for her.

**Kofi, ITG platform engineer.** Operates Frame, manages the event contract, builds integrations, handles migrations.

**Amara, external partner.** Touches Frame only through published forms and, later, composed apps. Never authenticates with a UNOPS account in v1.

## Cross-cutting non-functional requirements

These bind every PRD unless a PRD tightens them further.

**Performance.** Grid interactions under 100ms perceived latency at 10,000 loaded rows; view open under 1.5s p95; API reads under 300ms p95, writes under 500ms p95; form submission under 2s including validation.

**Availability.** 99.9% for the interactive service; automations may queue during degradation and must catch up without loss; Frame remains fully functional when Workflow Studio, Playbook, or any integration is unavailable.

**Security.** All permission trimming server-side. No client ever receives data the viewer is not entitled to, including via aggregates (annotated per the transparency principle) and search indexes. Immutable audit log for every write, permission change, export, and Blueprint edit. IAP plus OAuth, Google Identity only in v1.

**Data residency.** Our GCP project, our region (europe-west), CMEK on Firestore and Postgres for organizational-tier data.

**Accessibility.** WCAG 2.1 AA across the product, including the grid (this is a hard requirement that constrains the grid component choice; see PRD 11).

**Localization.** English at launch; string externalization from day one; Spanish and French as the first additional locales.

**Auditability of AI.** Every AI-generated artifact (Blueprint draft, formula, summary) is tagged as such in provenance metadata, with the prompt and model version retained per our AI governance framework.

## Configuration architecture: code-first

Frame follows the estate's multi-instance, code-first configuration model, which applies to application-level configuration only. Application configuration lives in the codebase as JSON or YAML (or in code where required); where runtime stores are appropriate (Postgres tables, Firestore documents), they are seeded from the in-code config at build time, so builds tagged to a git commit tell us exactly what application configuration is active in any environment. Admin interfaces read configuration (from JSON, YAML, or code via reflection) and allow UI editing for file-backed config, and always offer download of the updated JSON or YAML for return to the codebase, where it reseeds on the next build. The working cycle: try a configuration in dev, test, or UAT through the admin UI, export the updated file, commit it, and deploy properly.

**Application configuration (code-first):** the field type registry and metaschema, the automation action and trigger vocabularies, notification classes and platform defaults, the shared filter grammar definition, integration endpoints (the e-signature endpoints per DG-6 are the canonical example), permission rule vocabulary, data standards consumed by the promotion review, org branding themes, feature flags, and environment wiring.

**User-authored configuration and content (database-driven, all tiers):** Blueprints at every tier including organizational, rows, views, comments, automations, dashboards, document templates, catalog entries, bindings, and app definitions. These live in the environment's database (Firestore, and Postgres replicas where applicable), are authored and promoted through the product's own governance (the ladder, BP-15 through BP-19), and are expected and desired to differ per environment. Promotion to organizational tier is a database-level act governed by steward review, not a deployment; nothing user-authored rides a build.

The line, stated once: if it defines how Frame behaves as an application, it is code-first; if it is something users or stewards author within Frame, it is data.

## Conventions in these PRDs

Requirements are numbered per document (BP-1, GR-1, ...) and tagged P1/P2/P3 matching the vision's three phases. "Must" is normative. Open questions are collected at the end of each PRD and are genuinely open, not rhetorical.
