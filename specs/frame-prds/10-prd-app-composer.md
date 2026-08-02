# PRD 10: App Composer

## Purpose

The payoff of the Blueprint model: compose views, forms, dashboards, and pages into role-scoped applications with navigation and branding, no code. The floor under Grant+ style products: domain apps become configuration over governed Blueprints rather than projects.

## Scope

In: app definition, page types, navigation, audience scoping, branding, publishing, app-level analytics. Out: new data capabilities (apps compose existing surfaces only; if a capability is missing, it is built in its home PRD, never as an app special case). Out in v1: external unauthenticated apps beyond forms and status pages (P3 decision point). Out permanently: a third-party app runtime or marketplace — the strongest platform competitor needs 850+ marketplace apps because a semantically empty board cannot finish the job (87% of its enterprise accounts install apps to close gaps, by its own published figures), and hosting third-party code would re-import every review, sandboxing and permission problem Frame's composition model exists to avoid. Extension pressure routes to the MCP surface (AI-10) and the published event contract (AU-8), where external logic runs outside Frame's process under its own service identity.

## Functional requirements

**AC-1 (P3).** An app is a versioned configuration document: name, icon, brand theme, audience bindings, navigation tree, and pages. Apps live in a workspace, may reference organizational Blueprints, and publish to a stable URL under the Frame domain.

**AC-2 (P3).** Page types: view page (a saved view, optionally locked to its configuration), form page, dashboard page, record page (master-detail form for a Blueprint, reachable from view pages), and content page (rich text/markdown for guidance). Pages accept URL parameters for record routing.

**AC-3 (P3).** Audiences: named roles within the app (requester, reviewer, manager) bound to users/groups; navigation and pages scope per audience. Audience scoping composes with, and never overrides, PRD 05 evaluation: an app can narrow what an audience sees, never widen it. The composer surfaces effective-access preview per audience ("view as reviewer") so builders see the composed result before publishing.

**AC-4 (P3).** Publishing: draft and published versions, change preview, one-click rollback, and an app directory for discovery within the org (with the same attribution model: apps credit their builders).

**AC-5 (P3).** App analytics for builders: page views, form conversion, active users per audience, surfaced in a builder dashboard (privacy-reviewed metric set, no individual browsing surveillance).

**AC-6 (P3).** Templates: an app template gallery seeded with the patterns we know we need (intake and triage, register and review, portfolio room), instantiating apps bound to catalog Blueprints.

**AC-7 (P2).** Application templates. The catalog may package a Blueprint together with its named forms (FM-1), workflow states (AU-10), starter recipes (AU-14) and saved views (GR-11) as one **application template**: a catalog entry a workspace adopts in a single act, arriving with its intake, states, automations and views working rather than as a bare schema. Adoption is BP-19 binding, never copying, and each packaged artifact remains an instance of its own mechanism — a template introduces no new runtime and no new authoring surface, which is what makes it safe to pull ahead of the full composer: it is packaging over surfaces that exist at P2, not composition logic. Pulled forward from AC-6's P3 gallery by owner decision (August 2026, closing this PRD's former open question 4): the discovery evidence says the adoptable unit users want is the working application, not the schema, and the pilot set carries the proof case — a fleet register is an asset register with vehicle-specific additions, which is template-plus-overlay, not a second build. AC-6 remains P3 and extends this same mechanism to full multi-page apps; a second, parallel template mechanism would be one too many.

## Dependencies

Everything: PRDs 01 through 09 supply the composable surfaces. The composer ships last for exactly that reason, and its scope stays thin by design; the moment the composer needs its own data or logic capabilities, that pressure routes back to the platform PRDs.

## Open questions

1. External authenticated apps (partner logins beyond magic links): identity architecture decision with the PPP experience as prior art; deliberately deferred.
2. Whether apps can embed Playbook conversational surfaces as a page type; attractive for domain apps, sequenced after MCP maturity.
3. Custom domains per app (grants.unops.org style): estate DNS and certificate policy conversation, not a product blocker.

## Decisions log

Resolved August 2026:

- **Application templates pull to P2** (AC-7, closing former open question 4): decided by the repo owner following the discovery run's reframing; vision §9 Phase 2 amended accordingly. The full composer (AC-1..AC-5) stays P3 — the dependency argument below still holds for composition logic; AC-7 is packaging only.
